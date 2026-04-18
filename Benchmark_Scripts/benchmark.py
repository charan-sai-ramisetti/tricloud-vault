"""
benchmark.py — Cloud Storage Upload Performance Benchmark
==========================================================
Measures upload throughput for AWS S3, Azure Blob Storage, and GCP Cloud
Storage across two upload methods:

  server    — client → Django backend → cloud  (POST multipart/form-data)
  presigned — client → directly to cloud       (presigned / SAS / resumable URLs)

Two execution modes via --mode:
  isolated     — one cloud at a time (default, controls for interference)
  simultaneous — all 3 clouds in parallel via ThreadPoolExecutor

Usage
-----
    python benchmark.py --backend-url http://<django-host>/api/files
"""

import argparse
import csv
import logging
import os
import statistics
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
import shutil

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("benchmark")

# ---------------------------------------------------------------------------
# Experiment configuration
# ---------------------------------------------------------------------------
FILE_SIZES_MB     = [50, 100, 500, 1024, 2048, 5120]
CHUNK_SIZES_MB    = [5, 8, 10, 16, 25, 50, 100]
PROVIDERS         = ["AWS", "AZURE", "GCP"]
TOTAL_TRIALS      = 15
WARMUP_TRIALS     = 2
INTER_TRIAL_DELAY = 5
HTTP_TIMEOUT      = 7200
MAX_RETRIES       = 3
RETRY_BACKOFF     = 2.0
WRITE_BLOCK       = 4 * 1024 * 1024  # 4 MB write block for file generation

# throughput_MBps = megabytes per second (not megabits)
CSV_FIELDS = [
    "provider",
    "method",
    "mode",
    "file_size_mb",
    "chunk_size_mb",
    "trial",
    "total_time_s",
    "throughput_MBps",   # MB/s (megabytes per second, not megabits)
    "ttfb_s",
    "url_gen_s",
    "chunk_mean_s",
    "chunk_std_s",
    "retries",
    "failed_chunks",
]


# ---------------------------------------------------------------------------
# File generation
# ---------------------------------------------------------------------------

def check_disk_space(required_bytes: int, tmp_dir: Path) -> None:
    """Raise if available disk space is less than required_bytes."""
    available = shutil.disk_usage(tmp_dir).free
    if available < required_bytes:
        raise RuntimeError(
            f"Insufficient disk space in {tmp_dir}: "
            f"need {required_bytes // (1024**2)} MB, "
            f"have {available // (1024**2)} MB free"
        )


def generate_test_file(size_mb: int, tmp_dir: Path) -> Path:
    """
    Write size_mb MB of random bytes to a temp file.
    os.urandom() ensures incompressible data (avoids skewing throughput via compression).
    Written in 4 MB blocks to keep peak RAM bounded regardless of file size.
    """
    size_bytes = size_mb * 1024 * 1024
    check_disk_space(size_bytes, tmp_dir)

    file_path = tmp_dir / f"benchmark_{size_mb}mb_{uuid.uuid4().hex}.bin"
    logger.info(f"Generating {size_mb} MB test file → {file_path}")

    written = 0
    with open(file_path, "wb") as f:
        while written < size_bytes:
            block = min(WRITE_BLOCK, size_bytes - written)
            f.write(os.urandom(block))
            written += block

    return file_path


def cleanup_test_file(file_path: Path) -> None:
    try:
        file_path.unlink()
        logger.debug(f"Cleaned up: {file_path}")
    except OSError as e:
        logger.warning(f"Could not remove {file_path}: {e}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mb(n: int) -> int:
    return n * 1024 * 1024


def _throughput_MBps(file_size_bytes: int, elapsed_seconds: float) -> float:
    if elapsed_seconds <= 0:
        return 0.0
    return (file_size_bytes / (1024 * 1024)) / elapsed_seconds


def _chunk_stats(chunk_times: List[float]) -> Tuple[float, float]:
    if not chunk_times:
        return 0.0, 0.0
    mean = statistics.mean(chunk_times)
    std  = statistics.stdev(chunk_times) if len(chunk_times) > 1 else 0.0
    return mean, std


def _safe_json(resp: requests.Response) -> dict:
    """Parse JSON response safely; returns empty dict on failure."""
    try:
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to parse JSON response (status {resp.status_code}): {e}")
        return {}


# ---------------------------------------------------------------------------
# AWS chunk uploader — captures ETag from response headers
# ---------------------------------------------------------------------------

def _upload_aws_chunk(
    part_url: str,
    chunk_data: bytes,
) -> Tuple[str, float, float, int]:
    """
    PUT one S3 multipart part.
    Returns (etag, elapsed_s, ttfb_s, retry_count).
    ETag is taken from the response header — never use a placeholder value.

    Note: presigned part URLs are single-use. On retry the caller should
    ideally regenerate the URL. The current structure passes a pre-generated
    URL; for robustness in long uploads consider regenerating on each retry.
    """
    retry_count = 0
    last_error  = None

    for attempt in range(MAX_RETRIES):
        try:
            t_start = time.perf_counter()
            resp = requests.put(part_url, data=chunk_data, timeout=HTTP_TIMEOUT, stream=True)
            ttfb = time.perf_counter() - t_start
            resp.raise_for_status()
            _ = resp.content
            elapsed = time.perf_counter() - t_start
            etag = resp.headers.get("ETag", "").strip('"')
            return etag, elapsed, ttfb, retry_count

        except (requests.RequestException, OSError) as e:
            last_error = e
            retry_count += 1
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BACKOFF * (2 ** attempt)
                logger.warning(f"AWS chunk failed (attempt {attempt + 1}): {e}. Retry in {delay:.1f}s")
                time.sleep(delay)

    raise RuntimeError(f"AWS chunk failed after {MAX_RETRIES} attempts: {last_error}")


# ---------------------------------------------------------------------------
# Server-side upload
# ---------------------------------------------------------------------------

def _server_upload(
    backend_url: str,
    provider: str,
    file_path: Path,
    file_size_bytes: int,
    chunk_size: int,
) -> Dict:
    endpoint_map = {
        "AWS":   f"{backend_url}/upload/server/aws/",
        "AZURE": f"{backend_url}/upload/server/azure/",
        "GCP":   f"{backend_url}/upload/server/gcp/",
    }
    url = endpoint_map[provider]

    t_start = time.perf_counter()
    with open(file_path, "rb") as f:
        resp = requests.post(
            url,
            files={"file": (file_path.name, f, "application/octet-stream")},
            data={"chunk_size": chunk_size},
            timeout=HTTP_TIMEOUT,
        )
    wall_clock = time.perf_counter() - t_start
    resp.raise_for_status()

    result      = _safe_json(resp)
    server_time = result.get("upload_time_seconds", wall_clock)

    return {
        "total_time_s":    round(server_time, 6),
        "throughput_MBps": round(_throughput_MBps(file_size_bytes, server_time), 4),
        "ttfb_s":          0.0,
        "url_gen_s":       0.0,
        "chunk_mean_s":    0.0,
        "chunk_std_s":     0.0,
        "retries":         0,
        "failed_chunks":   0,
    }


# ---------------------------------------------------------------------------
# Presigned upload — AWS S3
# ---------------------------------------------------------------------------

def _presigned_upload_aws_full(
    backend_url: str,
    file_path: Path,
    file_size_bytes: int,
    chunk_size: int,
) -> Dict:
    """
    Full AWS presigned multipart upload with ETag capture, per-chunk timing,
    retry tracking, and TTFB measurement.
    Raises if any chunk permanently fails — never completes a partial upload.
    """
    t_url_start = time.perf_counter()
    resp = requests.post(
        f"{backend_url}/benchmark/presign/aws/",
        json={"file_size": file_size_bytes, "chunk_size": chunk_size, "file_name": file_path.name},
        timeout=30,
    )
    resp.raise_for_status()
    meta      = _safe_json(resp)
    url_gen_s = time.perf_counter() - t_url_start

    key            = meta["key"]
    upload_id      = meta["upload_id"]
    presigned_urls = meta["presigned_urls"]
    actual_chunk   = meta["chunk_size"]

    parts         = []
    chunk_times   = []
    total_retries = 0
    failed_chunks = 0
    first_ttfb    = None

    t_upload_start = time.perf_counter()

    with open(file_path, "rb") as f:
        for item in presigned_urls:
            part_number = item["part_number"]
            f.seek((part_number - 1) * actual_chunk)
            chunk_data = f.read(actual_chunk)

            try:
                etag, elapsed, ttfb, retries = _upload_aws_chunk(item["url"], chunk_data)
                chunk_times.append(elapsed)
                total_retries += retries
                if first_ttfb is None:
                    first_ttfb = ttfb
                parts.append({"PartNumber": part_number, "ETag": etag})

            except RuntimeError:
                logger.error(f"AWS chunk {part_number} permanently failed")
                failed_chunks += 1

    # Do not attempt to complete a partial upload — S3 would reject missing parts
    if failed_chunks > 0:
        raise RuntimeError(
            f"AWS upload aborted: {failed_chunks} chunk(s) failed after {MAX_RETRIES} retries"
        )

    complete_resp = requests.post(
        f"{backend_url}/multipart/complete/",
        json={"cloud": "AWS", "key": key, "upload_id": upload_id, "parts": parts},
        timeout=30,
    )
    complete_resp.raise_for_status()

    total_time = time.perf_counter() - t_upload_start
    chunk_mean, chunk_std = _chunk_stats(chunk_times)

    return {
        "total_time_s":    round(total_time, 6),
        "throughput_MBps": round(_throughput_MBps(file_size_bytes, total_time), 4),
        "ttfb_s":          round(first_ttfb or 0.0, 6),
        "url_gen_s":       round(url_gen_s, 6),
        "chunk_mean_s":    round(chunk_mean, 6),
        "chunk_std_s":     round(chunk_std, 6),
        "retries":         total_retries,
        "failed_chunks":   failed_chunks,
    }


# ---------------------------------------------------------------------------
# Presigned upload — Azure Blob Storage
# ---------------------------------------------------------------------------

def _upload_chunk_with_retry(
    put_url: str,
    chunk_data: bytes,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Tuple[float, float, int]:
    """
    PUT a single chunk with retry and TTFB measurement.
    Returns (elapsed_s, ttfb_s, retry_count).

    Note: presigned/SAS URLs are ideally regenerated on retry for robustness,
    but current callers pass pre-generated URLs. Acceptable for benchmarking
    where failures are rare; consider per-retry URL refresh for production use.
    """
    headers     = extra_headers or {}
    retry_count = 0
    last_error  = None

    for attempt in range(MAX_RETRIES):
        try:
            t_start = time.perf_counter()
            with requests.put(
                put_url, data=chunk_data, headers=headers,
                timeout=HTTP_TIMEOUT, stream=True,
            ) as resp:
                ttfb = time.perf_counter() - t_start
                resp.raise_for_status()
                _ = resp.content
            elapsed = time.perf_counter() - t_start
            return elapsed, ttfb, retry_count

        except (requests.RequestException, OSError) as e:
            last_error = e
            retry_count += 1
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BACKOFF * (2 ** attempt)
                logger.warning(f"Chunk failed (attempt {attempt + 1}): {e}. Retry in {delay:.1f}s")
                time.sleep(delay)

    raise RuntimeError(f"Chunk failed after {MAX_RETRIES} attempts: {last_error}")


def _presigned_upload_azure(
    backend_url: str,
    file_path: Path,
    file_size_bytes: int,
    chunk_size: int,
) -> Dict:
    """
    Azure Put Block + Put Block List pattern.
    Do NOT set x-ms-blob-type on block part uploads (?comp=block) —
    that header is only valid on single-blob PUTs and causes 400 InvalidBlobOrBlock.
    Raises if any block permanently fails.
    """
    t_url_start = time.perf_counter()
    resp = requests.post(
        f"{backend_url}/benchmark/presign/azure/",
        json={"file_size": file_size_bytes, "chunk_size": chunk_size, "file_name": file_path.name},
        timeout=30,
    )
    resp.raise_for_status()
    meta      = _safe_json(resp)
    url_gen_s = time.perf_counter() - t_url_start

    blob_name      = meta["blob_name"]
    block_ids      = meta["block_ids"]
    presigned_urls = meta["presigned_urls"]
    actual_chunk   = meta["chunk_size"]

    chunk_times   = []
    total_retries = 0
    failed_chunks = 0
    first_ttfb    = None

    t_upload_start = time.perf_counter()

    with open(file_path, "rb") as f:
        for item in presigned_urls:
            part_number = item["part_number"]
            f.seek((part_number - 1) * actual_chunk)
            chunk_data = f.read(actual_chunk)

            try:
                elapsed, ttfb, retries = _upload_chunk_with_retry(item["url"], chunk_data)
                chunk_times.append(elapsed)
                total_retries += retries
                if first_ttfb is None:
                    first_ttfb = ttfb

            except RuntimeError:
                logger.error(f"Azure block {part_number} permanently failed")
                failed_chunks += 1

    if failed_chunks > 0:
        raise RuntimeError(
            f"Azure upload aborted: {failed_chunks} block(s) failed after {MAX_RETRIES} retries"
        )

    commit_resp = requests.post(
        f"{backend_url}/multipart/complete/",
        json={"cloud": "AZURE", "blob_name": blob_name, "blocks": block_ids},
        timeout=30,
    )
    commit_resp.raise_for_status()

    total_time = time.perf_counter() - t_upload_start
    chunk_mean, chunk_std = _chunk_stats(chunk_times)

    return {
        "total_time_s":    round(total_time, 6),
        "throughput_MBps": round(_throughput_MBps(file_size_bytes, total_time), 4),
        "ttfb_s":          round(first_ttfb or 0.0, 6),
        "url_gen_s":       round(url_gen_s, 6),
        "chunk_mean_s":    round(chunk_mean, 6),
        "chunk_std_s":     round(chunk_std, 6),
        "retries":         total_retries,
        "failed_chunks":   failed_chunks,
    }


# ---------------------------------------------------------------------------
# Presigned upload — GCP (resumable upload protocol)
# ---------------------------------------------------------------------------

def _presigned_upload_gcp(
    backend_url: str,
    file_path: Path,
    file_size_bytes: int,
    chunk_size: int,
) -> Dict:
    """
    GCS resumable upload: sequential chunk PUTs with Content-Range headers.
    Content-Type must match the value baked into the signed URL signature —
    omitting it causes 403 MalformedSecurityHeader.
    GCS returns 308 Resume Incomplete until the final chunk (200/201).
    Raises if any chunk permanently fails.
    """
    t_url_start = time.perf_counter()
    resp = requests.post(
        f"{backend_url}/benchmark/presign/gcp/",
        json={"file_size": file_size_bytes, "chunk_size": chunk_size, "file_name": file_path.name},
        timeout=30,
    )
    resp.raise_for_status()
    meta      = _safe_json(resp)
    url_gen_s = time.perf_counter() - t_url_start

    session_uri  = meta["upload_id"]
    actual_chunk = meta["chunk_size"]  # already aligned to 256 KiB boundary

    chunk_times   = []
    total_retries = 0
    failed_chunks = 0
    first_ttfb    = None

    t_upload_start = time.perf_counter()
    offset      = 0
    chunk_index = 0

    with open(file_path, "rb") as f:
        while offset < file_size_bytes:
            end = min(offset + actual_chunk, file_size_bytes)
            f.seek(offset)
            chunk_data = f.read(end - offset)

            headers = {
                "Content-Range": f"bytes {offset}-{end - 1}/{file_size_bytes}",
                "Content-Type":  "application/octet-stream",
            }

            retry_count = 0
            last_error  = None
            success     = False

            for attempt in range(MAX_RETRIES):
                try:
                    t_chunk = time.perf_counter()
                    resp = requests.put(
                        session_uri, data=chunk_data, headers=headers,
                        timeout=HTTP_TIMEOUT, stream=True,
                    )
                    ttfb = time.perf_counter() - t_chunk

                    if resp.status_code not in (200, 201, 308):
                        resp.raise_for_status()

                    _ = resp.content
                    elapsed = time.perf_counter() - t_chunk
                    chunk_times.append(elapsed)
                    total_retries += retry_count
                    if first_ttfb is None:
                        first_ttfb = ttfb
                    success = True
                    break

                except (requests.RequestException, OSError) as e:
                    last_error = e
                    retry_count += 1
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_BACKOFF * (2 ** attempt)
                        logger.warning(f"GCP chunk {chunk_index} failed (attempt {attempt + 1}): {e}. Retry in {delay:.1f}s")
                        time.sleep(delay)

            if not success:
                logger.error(f"GCP chunk {chunk_index} permanently failed")
                failed_chunks += 1

            offset      += actual_chunk
            chunk_index += 1

    if failed_chunks > 0:
        raise RuntimeError(
            f"GCP upload aborted: {failed_chunks} chunk(s) failed after {MAX_RETRIES} retries"
        )

    total_time = time.perf_counter() - t_upload_start
    chunk_mean, chunk_std = _chunk_stats(chunk_times)

    return {
        "total_time_s":    round(total_time, 6),
        "throughput_MBps": round(_throughput_MBps(file_size_bytes, total_time), 4),
        "ttfb_s":          round(first_ttfb or 0.0, 6),
        "url_gen_s":       round(url_gen_s, 6),
        "chunk_mean_s":    round(chunk_mean, 6),
        "chunk_std_s":     round(chunk_std, 6),
        "retries":         total_retries,
        "failed_chunks":   failed_chunks,
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_PRESIGNED_HANDLERS = {
    "AWS":   _presigned_upload_aws_full,
    "AZURE": _presigned_upload_azure,
    "GCP":   _presigned_upload_gcp,
}


# ---------------------------------------------------------------------------
# Trial runner
# ---------------------------------------------------------------------------

def run_trial(
    backend_url: str,
    provider: str,
    method: str,
    file_path: Path,
    file_size_bytes: int,
    chunk_size: int,
) -> Dict:
    if method == "server":
        return _server_upload(backend_url, provider, file_path, file_size_bytes, chunk_size)
    elif method == "presigned":
        return _PRESIGNED_HANDLERS[provider](backend_url, file_path, file_size_bytes, chunk_size)
    else:
        raise ValueError(f"Unknown method: {method!r}")


# ---------------------------------------------------------------------------
# Isolated mode
# ---------------------------------------------------------------------------

def run_isolated(
    backend_url: str,
    providers: List[str],
    methods: List[str],
    file_sizes_mb: List[int],
    chunk_sizes_mb: List[int],
    total_trials: int,
    warmup_trials: int,
    delay: float,
    tmp_dir: Path,
) -> List[Dict]:
    rows         = []
    combinations = [
        (p, m, fs, cs)
        for p  in providers
        for m  in methods
        for fs in file_sizes_mb
        for cs in chunk_sizes_mb
    ]

    logger.info(
        f"ISOLATED MODE: {len(combinations)} configurations × "
        f"{total_trials} trials ({warmup_trials} warmup)"
    )

    file_cache: Dict[int, Path] = {}

    for cfg_idx, (provider, method, file_size_mb, chunk_size_mb) in enumerate(combinations, 1):
        file_size_bytes = _mb(file_size_mb)
        chunk_size      = _mb(chunk_size_mb)

        if file_size_mb not in file_cache:
            file_cache[file_size_mb] = generate_test_file(file_size_mb, tmp_dir)
        file_path = file_cache[file_size_mb]

        logger.info(
            f"[{cfg_idx}/{len(combinations)}] "
            f"{provider} / {method} / {file_size_mb} MB / chunk {chunk_size_mb} MB"
        )

        trial_num = 0
        for t in range(total_trials):
            try:
                metrics = run_trial(backend_url, provider, method, file_path, file_size_bytes, chunk_size)
            except Exception as exc:
                logger.error(f"  Trial {t + 1} FAILED: {exc}")
                time.sleep(delay)
                continue

            is_warmup = t < warmup_trials
            flag      = "WARMUP" if is_warmup else "OK"
            logger.info(
                f"  Trial {t + 1:02d}/{total_trials} [{flag}]  "
                f"{metrics['total_time_s']:.3f}s  {metrics['throughput_MBps']:.2f} MB/s  "
                f"TTFB={metrics['ttfb_s']:.3f}s  retries={metrics['retries']}"
            )

            if not is_warmup:
                trial_num += 1
                rows.append({
                    "provider":      provider,
                    "method":        method,
                    "mode":          "isolated",
                    "file_size_mb":  file_size_mb,
                    "chunk_size_mb": chunk_size_mb,
                    "trial":         trial_num,
                    **metrics,
                })

            if t < total_trials - 1:
                time.sleep(delay)

    for fp in file_cache.values():
        cleanup_test_file(fp)

    return rows


# ---------------------------------------------------------------------------
# Simultaneous mode
# ---------------------------------------------------------------------------

def _run_single_provider_trial(args: Tuple) -> Tuple[str, str, Optional[Dict], Optional[str]]:
    backend_url, provider, method, file_path, file_size_bytes, chunk_size = args
    try:
        metrics = run_trial(backend_url, provider, method, file_path, file_size_bytes, chunk_size)
        return provider, method, metrics, None
    except Exception as e:
        return provider, method, None, str(e)


def run_simultaneous(
    backend_url: str,
    providers: List[str],
    methods: List[str],
    file_sizes_mb: List[int],
    chunk_sizes_mb: List[int],
    total_trials: int,
    warmup_trials: int,
    delay: float,
    tmp_dir: Path,
) -> List[Dict]:
    """
    All providers upload in parallel per trial — measures multi-cloud
    interference effect vs isolated mode.
    """
    rows         = []
    combinations = [
        (m, fs, cs)
        for m  in methods
        for fs in file_sizes_mb
        for cs in chunk_sizes_mb
    ]

    logger.info(
        f"SIMULTANEOUS MODE: {len(combinations)} configurations × "
        f"{total_trials} trials × {len(providers)} providers in parallel"
    )

    file_cache: Dict[int, Path] = {}

    for cfg_idx, (method, file_size_mb, chunk_size_mb) in enumerate(combinations, 1):
        file_size_bytes = _mb(file_size_mb)
        chunk_size      = _mb(chunk_size_mb)

        if file_size_mb not in file_cache:
            file_cache[file_size_mb] = generate_test_file(file_size_mb, tmp_dir)
        file_path = file_cache[file_size_mb]

        logger.info(
            f"[{cfg_idx}/{len(combinations)}] "
            f"SIMULTANEOUS / {method} / {file_size_mb} MB / chunk {chunk_size_mb} MB"
        )

        trial_num = 0
        for t in range(total_trials):
            is_warmup = t < warmup_trials
            flag      = "WARMUP" if is_warmup else "OK"

            worker_args = [
                (backend_url, provider, method, file_path, file_size_bytes, chunk_size)
                for provider in providers
            ]

            trial_results: Dict[str, Dict] = {}
            with ThreadPoolExecutor(max_workers=len(providers)) as executor:
                futures = {
                    executor.submit(_run_single_provider_trial, a): a[1]
                    for a in worker_args
                }
                for future in as_completed(futures):
                    provider, _, metrics, error = future.result()
                    if error:
                        logger.error(f"  [{flag}] {provider} trial {t + 1} FAILED: {error}")
                    else:
                        trial_results[provider] = metrics
                        logger.info(
                            f"  [{flag}] {provider} trial {t + 1:02d}/{total_trials}  "
                            f"{metrics['total_time_s']:.3f}s  {metrics['throughput_MBps']:.2f} MB/s"
                        )

            if not is_warmup:
                trial_num += 1
                for provider, metrics in trial_results.items():
                    rows.append({
                        "provider":      provider,
                        "method":        method,
                        "mode":          "simultaneous",
                        "file_size_mb":  file_size_mb,
                        "chunk_size_mb": chunk_size_mb,
                        "trial":         trial_num,
                        **metrics,
                    })

            if t < total_trials - 1:
                time.sleep(delay)

    for fp in file_cache.values():
        cleanup_test_file(fp)

    return rows


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _print_summary(rows: List[Dict]) -> None:
    from collections import defaultdict

    agg = defaultdict(list)
    for r in rows:
        key = (r["provider"], r["method"], r["mode"], r["file_size_mb"])
        agg[key].append(r["throughput_MBps"])

    print("\n" + "=" * 90)
    print(
        f"{'Provider':<8}  {'Method':<10}  {'Mode':<13}  {'File MB':>8}  "
        f"{'Trials':>6}  {'Avg MB/s':>9}  {'Min MB/s':>9}  {'Max MB/s':>9}"
    )
    print("-" * 90)

    for key in sorted(agg.keys()):
        provider, method, mode, file_mb = key
        vals = agg[key]
        avg  = statistics.mean(vals)
        print(
            f"{provider:<8}  {method:<10}  {mode:<13}  {file_mb:>8}  "
            f"{len(vals):>6}  {avg:>9.2f}  {min(vals):>9.2f}  {max(vals):>9.2f}"
        )

    print("=" * 90 + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_benchmark(args: argparse.Namespace) -> None:
    backend_url = args.backend_url.rstrip("/")
    output_path = Path(args.output)
    tmp_dir     = Path(args.tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    rows = []

    if args.mode in ("isolated", "both"):
        rows.extend(run_isolated(
            backend_url=backend_url,
            providers=args.providers,
            methods=args.methods,
            file_sizes_mb=args.file_sizes_mb,
            chunk_sizes_mb=args.chunk_sizes_mb,
            total_trials=args.trials,
            warmup_trials=args.warmup,
            delay=args.delay,
            tmp_dir=tmp_dir,
        ))

    if args.mode in ("simultaneous", "both"):
        rows.extend(run_simultaneous(
            backend_url=backend_url,
            providers=args.providers,
            methods=args.methods,
            file_sizes_mb=args.file_sizes_mb,
            chunk_sizes_mb=args.chunk_sizes_mb,
            total_trials=args.trials,
            warmup_trials=args.warmup,
            delay=args.delay,
            tmp_dir=tmp_dir,
        ))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Results written to {output_path}  ({len(rows)} rows)")
    _print_summary(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cloud storage upload benchmark — AWS / Azure / GCP"
    )
    parser.add_argument(
        "--backend-url",
        default=os.getenv("BENCHMARK_BACKEND_URL", "http://localhost:8000/api/files"),
    )
    parser.add_argument("--output",  default="results/benchmark_results.csv")
    parser.add_argument("--tmp-dir", default="/tmp/benchmark_files",
                        help="Directory for temp files — needs space for the largest file size")
    parser.add_argument(
        "--mode", choices=["isolated", "simultaneous", "both"], default="both",
    )
    parser.add_argument("--providers", nargs="+", choices=["AWS", "AZURE", "GCP"],
                        default=list(PROVIDERS))
    parser.add_argument("--methods",   nargs="+", choices=["server", "presigned"],
                        default=["server", "presigned"])
    parser.add_argument("--file-sizes-mb",  nargs="+", type=int,
                        default=list(FILE_SIZES_MB), metavar="MB")
    parser.add_argument("--chunk-sizes-mb", nargs="+", type=int,
                        default=list(CHUNK_SIZES_MB), metavar="MB")
    parser.add_argument("--trials",  type=int, default=TOTAL_TRIALS)
    parser.add_argument("--warmup",  type=int, default=WARMUP_TRIALS)
    parser.add_argument("--delay",   type=float, default=INTER_TRIAL_DELAY)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    run_benchmark(args)