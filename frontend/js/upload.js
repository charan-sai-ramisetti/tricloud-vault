let lastUploadMeta = null;
let uploadResults = {};

/* ===============================
   FILE INPUT CHANGE HANDLER
   =============================== */
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
   HARD RESET UPLOAD FORM
   =============================== */
function resetUploadForm() {
  const wrapper = document.getElementById("file-input-wrapper");
  if (!wrapper) return;

  wrapper.innerHTML = `
    <label class="file-picker">
      <input type="file" id="fileInput" hidden />
      <span id="selected-file-text">Select file</span>
    </label>
  `;

  const checkboxes = document.querySelectorAll(
    "#cloudSelect input[type='checkbox']"
  );
  checkboxes.forEach(cb => (cb.checked = false));
}

/* ===============================
   SAFE BUTTON HANDLER
   =============================== */
function setUploadButton(disabled, text) {
  const btn = document.getElementById("uploadBtn");
  if (!btn) return;

  btn.disabled = disabled;
  if (text) btn.innerText = text;
}

/* ===============================
   START UPLOAD
   =============================== */
function startUpload() {
  setUploadButton(true, "Uploading...");

  const fileInput = document.getElementById("fileInput");
  const cloudCheckboxes = document.querySelectorAll(
    "#cloudSelect input[type='checkbox']:checked"
  );

  if (!fileInput || !fileInput.files.length) {
    alert("Please select a file");
    setUploadButton(false, "Upload");
    return;
  }

  if (cloudCheckboxes.length === 0) {
    alert("Please select at least one cloud");
    setUploadButton(false, "Upload");
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
      file_type: file.type,
      clouds: clouds
    })
  })
    .then(res => res.json())
    .then(data => {
      if (!data.upload_urls || !data.paths) {
        throw new Error("Invalid presign response");
      }

      uploadResults = {};
      clouds.forEach(c => (uploadResults[c] = false));

      lastUploadMeta = {
        file_name: file.name,
        file_size: file.size,
        aws_path: null,
        azure_path: null,
        gcp_path: null
      };

      const uploadPromises = clouds.map(cloud =>
        uploadToCloudParallel(file, cloud, data.upload_urls[cloud])
          .then(() => {
            uploadResults[cloud] = true;

            if (cloud === "AWS") lastUploadMeta.aws_path = data.paths.aws_path;
            if (cloud === "AZURE") lastUploadMeta.azure_path = data.paths.azure_path;
            if (cloud === "GCP") lastUploadMeta.gcp_path = data.paths.gcp_path;
          })
          .catch(() => {
            uploadResults[cloud] = false;
          })
      );

      Promise.allSettled(uploadPromises).then(() => {
        const successClouds = Object.keys(uploadResults).filter(
          c => uploadResults[c]
        );

        if (successClouds.length === 0) {
          alert("Upload failed on all selected clouds");
          setUploadButton(false, "Upload");
          return;
        }

        confirmUpload(successClouds);
      });
    })
    .catch(err => {
      console.error(err);
      alert("Failed to start upload");
      setUploadButton(false, "Upload");
    });
}

/* ===============================
   PARALLEL UPLOAD HANDLER
   =============================== */
function uploadToCloudParallel(file, cloud, uploadUrl) {
  return new Promise((resolve, reject) => {
    const container = document.getElementById("upload-status-container");
    if (!container) {
      reject();
      return;
    }

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

    const progressEl = statusBox.querySelector(".progress");
    const statusText = statusBox.querySelector(".status-text");

    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl, true);

    if (uploadUrl.includes("blob.core.windows.net")) {
      xhr.setRequestHeader("x-ms-blob-type", "BlockBlob");
    }
    if (uploadUrl.includes("storage.googleapis.com")) {
      xhr.setRequestHeader("Content-Type", "application/octet-stream");
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

        setTimeout(() => {
          statusBox.remove();
          if (container.querySelectorAll(".upload-status").length === 0 && title) {
            title.remove();
          }
        }, 500);

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
   CONFIRM UPLOAD
   =============================== */
function confirmUpload(successClouds) {
  const payload = {
    file_name: lastUploadMeta.file_name,
    file_size: lastUploadMeta.file_size
  };

  if (successClouds.includes("AWS")) payload.aws_path = lastUploadMeta.aws_path;
  if (successClouds.includes("AZURE")) payload.azure_path = lastUploadMeta.azure_path;
  if (successClouds.includes("GCP")) payload.gcp_path = lastUploadMeta.gcp_path;

  fetch(`${API_BASE_URL}/files/confirm-upload/`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload)
  })
    .then(res => {
      if (!res.ok) throw new Error("Confirm upload failed");
      return res.json();
    })
    .then(() => {
      loadFiles();
      loadRecentFiles();
      loadFolders();
      loadStorageSummary();

      resetUploadForm();

      const container = document.getElementById("upload-status-container");
      if (container) container.innerHTML = "";

      setUploadButton(false, "Upload");
    })
    .catch(err => {
      console.error(err);
      alert("Upload verification failed");
      setUploadButton(false, "Upload");
    });
}
