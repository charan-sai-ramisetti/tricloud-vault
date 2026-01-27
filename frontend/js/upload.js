let lastUploadMeta = null;

/* ===============================
   START UPLOAD
   =============================== */
function startUpload() {
  const fileInput = document.getElementById("fileInput");
  const cloudCheckboxes = document.querySelectorAll(
    "#cloudSelect input[type='checkbox']:checked"
  );

  if (!fileInput.files.length) {
    alert("Please select a file");
    return;
  }

  if (cloudCheckboxes.length === 0) {
    alert("Please select at least one cloud");
    return;
  }

  const file = fileInput.files[0];
  const clouds = Array.from(cloudCheckboxes).map(cb => cb.value);

  fetch(`${API_BASE_URL}/files/presign/upload/`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      file_name: file.name,
      file_size: file.size,
      clouds: clouds
    })
  })
    .then(res => res.json())
    .then(data => {
      if (!data.upload_urls || !data.paths) {
        alert("Invalid presign response");
        return;
      }

      lastUploadMeta = {
        file_name: file.name,
        file_size: file.size,
        aws_path: data.paths.aws_path || null,
        azure_path: data.paths.azure_path || null,
        gcp_path: data.paths.gcp_path || null
      };

      // 🔥 PARALLEL uploads
      const uploadPromises = clouds.map(cloud =>
        uploadToCloudParallel(file, cloud, data.upload_urls[cloud])
      );

      Promise.allSettled(uploadPromises).then(results => {
        const successCount = results.filter(r => r.status === "fulfilled").length;

        if (successCount === 0) {
          alert("Upload failed on all clouds");
          return;
        }

        confirmUpload(); // ✅ called ONCE
      });
    })
    .catch(err => {
      console.error(err);
      alert("Failed to get presigned URL");
    });
}

/* ===============================
   PARALLEL UPLOAD HANDLER
   =============================== */
function uploadToCloudParallel(file, cloud, uploadUrl) {
  return new Promise((resolve, reject) => {
    const container = document.getElementById("upload-status-container");

    const statusBox = document.createElement("div");
    statusBox.className = "upload-status";
    statusBox.innerHTML = `
      <strong>${file.name} (${cloud})</strong>
      <div class="progress-bar">
        <div class="progress"></div>
      </div>
      <div class="status-text">Uploading...</div>
    `;
    container.appendChild(statusBox);

    const progressEl = statusBox.querySelector(".progress");
    const statusText = statusBox.querySelector(".status-text");

    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl, true);

    // Azure
    if (uploadUrl.includes("blob.core.windows.net")) {
      xhr.setRequestHeader("x-ms-blob-type", "BlockBlob");
    }

    // GCP
    if (uploadUrl.includes("storage.googleapis.com")) {
      xhr.setRequestHeader("Content-Type", "application/octet-stream");
    }

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        progressEl.style.width = percent + "%";
      }
    };

    xhr.onload = () => {
      if (xhr.status === 200 || xhr.status === 201) {
        statusText.innerText = "Uploaded ✅";
        resolve();
      } else {
        statusText.innerText = "Failed ❌";
        reject();
      }
    };

    xhr.onerror = () => {
      statusText.innerText = "Failed ❌";
      reject();
    };

    xhr.send(file);
  });
}

/* ===============================
   CONFIRM UPLOAD
   =============================== */
function confirmUpload() {
  fetch(`${API_BASE_URL}/files/confirm-upload/`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(lastUploadMeta)
  })
    .then(res => res.json())
    .then(() => {
      loadFiles();
    })
    .catch(err => {
      console.error(err);
      alert("Upload verification failed");
    });
}
