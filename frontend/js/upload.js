let lastUploadMeta = null;
let uploadResults = {};

const CHUNK_SIZE = 10 * 1024 * 1024;   // 10 MB — matches AWS SDK default, gives real progress granularity
const MAX_PARALLEL_UPLOADS = 3;
const BREATHING_DELAY = 50;             // 50 ms — enough to yield the event loop without killing throughput


/* ===============================
   FILE LABEL
================================ */
document.addEventListener("change", function (e) {

  if (e.target && e.target.id === "fileInput") {

    const label = document.getElementById("selected-file-text");

    if (!label) return;

    if (e.target.files.length > 0) {
      label.innerText = e.target.files[0].name;
    } else {
      label.innerText = "Select file";
    }

  }

});


/* ===============================
   BUTTON CONTROL
================================ */
function setUploadButton(disabled, text) {

  const btn = document.getElementById("uploadBtn");

  if (!btn) return;

  btn.disabled = disabled;

  if (text) btn.innerText = text;

}


/* ===============================
   RESET FORM
================================ */
function resetUploadForm() {

  const wrapper = document.getElementById("file-input-wrapper");

  if (!wrapper) return;

  wrapper.innerHTML = `
    <label class="file-picker">
      <input type="file" id="fileInput" hidden />
      <span id="selected-file-text">Select file</span>
    </label>
  `;

  document
    .querySelectorAll("#cloudSelect input[type='checkbox']")
    .forEach(cb => (cb.checked = false));

}


/* ===============================
   CREATE STATUS BOX
================================ */
function createStatusBox(file, cloud) {

  const container = document.getElementById("upload-status-container");

  let title = container.querySelector(".upload-title");

  if (!title) {

    title = document.createElement("div");
    title.className = "upload-title";
    title.innerHTML = `<strong>${file.name}</strong>`;
    container.appendChild(title);

  }

  const statusBox = document.createElement("div");

  statusBox.className = "upload-status";

  statusBox.innerHTML = `
    <strong>${cloud}</strong>
    <div class="progress-bar">
      <div class="progress"></div>
    </div>
    <div class="status-text">Uploading… 0%</div>
  `;

  container.appendChild(statusBox);

  return statusBox;

}


/* ===============================
   START UPLOAD
================================ */
function startUpload() {

  setUploadButton(true, "Uploading...");

  const fileInput = document.getElementById("fileInput");

  const selectedClouds = document.querySelectorAll(
    "#cloudSelect input[type='checkbox']:checked"
  );

  if (!fileInput || !fileInput.files.length) {

    alert("Please select a file");

    setUploadButton(false, "Upload");

    return;

  }

  if (selectedClouds.length === 0) {

    alert("Please select at least one cloud");

    setUploadButton(false, "Upload");

    return;

  }

  const file = fileInput.files[0];

  const clouds = Array.from(selectedClouds).map(cb => cb.value);

  fetch(`${API_BASE_URL}/files/presign/upload/`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      file_name: file.name,
      file_size: file.size,
      file_type: file.type,
      clouds: clouds
    })
  })
    .then(res => res.json())
    .then(data => {

      if (data.upload_type === "single") {

        startSingleUpload(file, clouds, data);

      } else {

        startMultipartUpload(file, clouds);

      }

    })
    .catch(err => {

      console.error(err);

      alert("Upload failed");

      setUploadButton(false, "Upload");

    });

}


/* ===============================
   SINGLE UPLOAD
================================ */
function startSingleUpload(file, clouds, data) {

  uploadResults = {};
  clouds.forEach(c => uploadResults[c] = false);

  lastUploadMeta = {
    file_name: file.name,
    file_size: file.size,
    aws_path: null,
    azure_path: null,
    gcp_path: null
  };

  const uploads = clouds.map(cloud => {

    const box = createStatusBox(file, cloud);

    return uploadSingleFile(file, cloud, data.upload_urls[cloud], box)
      .then(() => {

        uploadResults[cloud] = true;

        if (cloud === "AWS") lastUploadMeta.aws_path = data.paths.aws_path;
        if (cloud === "AZURE") lastUploadMeta.azure_path = data.paths.azure_path;
        if (cloud === "GCP") lastUploadMeta.gcp_path = data.paths.gcp_path;

      });

  });

  Promise.allSettled(uploads).then(() => {

    const success = Object.keys(uploadResults).filter(c => uploadResults[c]);

    if (success.length === 0) {

      alert("Upload failed");

      setUploadButton(false, "Upload");

      return;

    }

    confirmUpload(success);

  });

}


/* ===============================
   SINGLE FILE UPLOAD
================================ */
function uploadSingleFile(file, cloud, uploadUrl, statusBox) {

  return new Promise((resolve, reject) => {

    const progressEl = statusBox.querySelector(".progress");
    const statusText = statusBox.querySelector(".status-text");

    const xhr = new XMLHttpRequest();

    xhr.open("PUT", uploadUrl, true);

    // x-ms-blob-type is required ONLY for single-blob PUTs (not block part uploads)
    if (cloud === "AZURE") {
      xhr.setRequestHeader("x-ms-blob-type", "BlockBlob");
    }

    xhr.upload.onprogress = e => {

      if (e.lengthComputable) {

        const percent = Math.round((e.loaded / e.total) * 100);

        progressEl.style.width = percent + "%";

        statusText.innerText = `Uploading… ${percent}%`;

      }

    };

    xhr.onload = () => {

      if (xhr.status === 200 || xhr.status === 201) {

        progressEl.style.width = "100%";

        statusText.innerText = "Uploaded";

        resolve();

      } else {

        statusText.innerText = "Failed";

        reject();

      }

    };

    xhr.onerror = () => {

      statusText.innerText = "Failed";

      reject();

    };

    xhr.send(file);

  });

}


/* ===============================
   MULTIPART UPLOAD
================================ */
async function startMultipartUpload(file, clouds) {

  lastUploadMeta = {
    file_name: file.name,
    file_size: file.size,
    aws_path: null,
    azure_path: null,
    gcp_path: null
  };

  const uploads = clouds.map(cloud => multipartForCloud(file, cloud));

  const results = await Promise.allSettled(uploads);

  const success = [];

  results.forEach((r, i) => {

    if (r.status === "fulfilled") success.push(clouds[i]);

  });

  if (success.length === 0) {

    alert("Upload failed");

    setUploadButton(false, "Upload");

    return;

  }

  confirmUpload(success);

}


/* ===============================
   MULTIPART PER CLOUD
================================ */
async function multipartForCloud(file, cloud) {

  const statusBox = createStatusBox(file, cloud);

  const progressEl = statusBox.querySelector(".progress");
  const statusText = statusBox.querySelector(".status-text");

  // START MULTIPART
  const start = await fetch(`${API_BASE_URL}/files/multipart/start/`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      file_name: file.name,
      file_type: file.type,
      cloud: cloud
    })
  });

  const startData = await start.json();

  const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

  // Byte-accurate progress: track how many bytes each chunk has uploaded so far
  const bytesUploadedPerChunk = new Array(totalChunks).fill(0);
  const chunkSizes = [];
  for (let i = 0; i < totalChunks; i++) {
    const start = i * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, file.size);
    chunkSizes.push(end - start);
  }

  function onChunkProgress(chunkIndex, bytesLoaded) {
    bytesUploadedPerChunk[chunkIndex] = bytesLoaded;
    const totalUploaded = bytesUploadedPerChunk.reduce((a, b) => a + b, 0);
    // Cap at 99% until the commit step succeeds
    const percent = Math.min(99, Math.round((totalUploaded / file.size) * 100));
    progressEl.style.width = percent + "%";
    statusText.innerText = `Uploading… ${percent}%`;
  }

  const parts = [];

  // UPLOAD CHUNKS in batches of MAX_PARALLEL_UPLOADS
  for (let i = 0; i < totalChunks; i += MAX_PARALLEL_UPLOADS) {

    const batch = [];

    for (let j = i; j < i + MAX_PARALLEL_UPLOADS && j < totalChunks; j++) {

      batch.push(uploadChunk(file, cloud, startData, j, onChunkProgress));

    }

    const results = await Promise.all(batch);

    parts.push(...results);

    await sleep(BREATHING_DELAY);

  }

  // COMPLETE MULTIPART

  if (cloud === "AWS") {

    const completeRes = await fetch(`${API_BASE_URL}/files/multipart/complete/`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        cloud: cloud,
        key: startData.key,
        upload_id: startData.upload_id,
        parts: parts
      })
    });

    if (!completeRes.ok) {
      throw new Error("AWS multipart complete failed");
    }

    lastUploadMeta.aws_path = startData.key;

  }

  if (cloud === "AZURE") {

    const completeRes = await fetch(`${API_BASE_URL}/files/multipart/complete/`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        cloud: cloud,
        blob_name: startData.blob_name,
        blocks: parts.map(p => p.block_id)
      })
    });

    if (!completeRes.ok) {
      throw new Error("Azure block commit failed");
    }

    lastUploadMeta.azure_path = startData.blob_name;

  }

  if (cloud === "GCP") {

    // GCP resumable uploads complete automatically
    lastUploadMeta.gcp_path = startData.blob;

  }

  progressEl.style.width = "100%";
  statusText.innerText = "Uploaded";

}


/* ===============================
   UPLOAD CHUNK
================================ */
function uploadChunk(file, cloud, startData, index, onProgress) {

  return new Promise(async (resolve, reject) => {

    try {

      const start = index * CHUNK_SIZE;
      const end = Math.min(start + CHUNK_SIZE, file.size);
      const chunk = file.slice(start, end);

      let payload;
      let blockId = null;

      // ===============================
      // AWS Multipart Upload
      // ===============================
      if (cloud === "AWS") {

        payload = {
          cloud: cloud,
          key: startData.key,
          upload_id: startData.upload_id,
          part_number: index + 1
        };

      }

      // ===============================
      // Azure Block Upload
      // ===============================
      if (cloud === "AZURE") {

        blockId = btoa(String(index + 1).padStart(6, "0"));

        payload = {
          cloud: cloud,
          blob_name: startData.blob_name,
          block_id: blockId
        };

      }

      // ===============================
      // Request presigned upload URL
      // ===============================
      const presign = await fetch(`${API_BASE_URL}/files/multipart/presign-part/`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(payload)
      });

      const presignData = await presign.json();

      if (!presignData.url) {
        reject("Failed to generate upload URL");
        return;
      }

      const xhr = new XMLHttpRequest();

      xhr.open("PUT", presignData.url, true);

      // NOTE: Do NOT set x-ms-blob-type on block part uploads (?comp=block).
      // That header is only valid for single-blob PUTs. Setting it on block
      // part requests causes Azure to reject the upload.

      // Wire up per-chunk progress for byte-accurate overall progress tracking
      xhr.upload.onprogress = e => {
        if (e.lengthComputable && onProgress) {
          onProgress(index, e.loaded);
        }
      };

      xhr.onload = () => {

        if (xhr.status === 200 || xhr.status === 201) {

          // Mark this chunk as fully uploaded
          if (onProgress) {
            const chunkSize = end - start;
            onProgress(index, chunkSize);
          }

          const etag = xhr.getResponseHeader("ETag");

          // AWS result
          if (cloud === "AWS") {
            resolve({
              ETag: etag,
              PartNumber: index + 1
            });
          }

          // Azure result
          if (cloud === "AZURE") {
            resolve({
              block_id: blockId
            });
          }

        } else {
          reject(`Upload failed with status ${xhr.status}`);
        }

      };

      xhr.onerror = () => reject("Upload failed");

      xhr.send(chunk);

    } catch (err) {

      reject(err);

    }

  });

}

/* ===============================
   CONFIRM UPLOAD
================================ */
function confirmUpload(successClouds) {

  const payload = {
    file_name: lastUploadMeta.file_name,
    file_size: lastUploadMeta.file_size
  };

  if (successClouds.includes("AWS"))
    payload.aws_path = lastUploadMeta.aws_path;

  if (successClouds.includes("AZURE"))
    payload.azure_path = lastUploadMeta.azure_path;

  if (successClouds.includes("GCP"))
    payload.gcp_path = lastUploadMeta.gcp_path;

  fetch(`${API_BASE_URL}/files/confirm-upload/`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload)
  })
    .then(() => {

      loadFiles();
      loadRecentFiles();
      loadFolders();
      loadStorageSummary();

      resetUploadForm();

      document.getElementById("upload-status-container").innerHTML = "";

      setUploadButton(false, "Upload");

    })
    .catch(() => {

      alert("Upload verification failed");

      setUploadButton(false, "Upload");

    });

}


/* ===============================
   SLEEP
================================ */
function sleep(ms) {

  return new Promise(resolve => setTimeout(resolve, ms));

}