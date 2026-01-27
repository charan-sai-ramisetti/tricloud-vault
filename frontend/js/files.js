// Load files when dashboard opens
document.addEventListener("DOMContentLoaded", loadFiles);

function loadFiles() {
  fetch(`${API_BASE_URL}/files/`, {
    method: "GET",
    headers: authHeaders()
  })
    .then(res => res.json())
    .then(data => {
      const table = document.getElementById("filesTable");
      table.innerHTML = "";

      data.forEach(file => {
        const clouds = [];

        if (file.aws_path) clouds.push("AWS");
        if (file.azure_path) clouds.push("Azure");
        if (file.gcp_path) clouds.push("GCP");

        const row = document.createElement("tr");

        row.innerHTML = `
          <td>${file.file_name}</td>
          <td>${clouds.join(", ")}</td>
          <td>
            <button class="download" onclick="downloadFile(${file.id})">
              Download
            </button>
            <button class="delete" onclick='deleteFile(${file.id}, ${JSON.stringify(clouds)})'>
              Delete
            </button>
          </td>
        `;

        table.appendChild(row);
      });
    })
    .catch(() => alert("Failed to load files"));
}

/* ===============================
   DOWNLOAD FILE
   =============================== */
function downloadFile(fileId) {
  fetch(`${API_BASE_URL}/files/${fileId}/presign/download/`, {
    method: "GET",
    headers: authHeaders()
  })
    .then(res => res.json())
    .then(data => {
      window.open(data.download_url, "_blank");
    })
    .catch(() => alert("Download failed"));
}

/* ===============================
   DELETE FILE (CLOUD-AWARE)
   =============================== */
function deleteFile(fileId, clouds) {
  if (!clouds || clouds.length === 0) {
    alert("No clouds found for this file");
    return;
  }

  const selected = prompt(
    `File exists in: ${clouds.join(", ")}\n\n` +
    `Type clouds to delete (comma separated), or ALL:\n` +
    `Example: AWS,GCP`
  );

  if (!selected) return;

  let deleteClouds;

  if (selected.toUpperCase() === "ALL") {
    deleteClouds = clouds;
  } else {
    deleteClouds = selected
      .split(",")
      .map(c => c.trim().toUpperCase())
      .filter(c =>
        clouds.map(x => x.toUpperCase()).includes(c)
      );
  }

  if (deleteClouds.length === 0) {
    alert("No valid clouds selected");
    return;
  }

  fetch(`${API_BASE_URL}/files/${fileId}/`, {
    method: "DELETE",
    headers: authHeaders(),
    body: JSON.stringify({
      clouds: deleteClouds
    })
  })
    .then(() => {
      loadFiles();
    })
    .catch(() => alert("Delete failed"));
}
