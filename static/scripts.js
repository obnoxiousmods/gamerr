const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
const downloads = {};

function showDownloads() {
  document.getElementById('downloadsModal').style.display = 'block';
}
function hideDownloads() {
  document.getElementById('downloadsModal').style.display = 'none';
}

function updateDownloadUI(id, name, percent, status) {
  const container = document.getElementById("downloadsContainer");
  if (!downloads[id]) {
    const div = document.createElement("div");
    div.className = "field-row-stacked";
    div.id = `dl-${id}`;

    const label = document.createElement("label");
    label.textContent = name;
    label.className = "dl-label";

    const progress = document.createElement("progress");
    progress.value = percent || 0;
    progress.max = 100;

    div.appendChild(label);
    div.appendChild(progress);
    container.appendChild(div);

    downloads[id] = { div, label, progress };
  }

  downloads[id].progress.value = percent;
  if (status === "completed") {
    downloads[id].label.textContent = `${name} ✅ Done`;
  } else if (status === "error") {
    downloads[id].label.textContent = `${name} ❌ Error`;
  }
}

function doSearch() {
  const btn = document.getElementById("searchBtn");
  const q = document.getElementById("searchBox").value.trim();
  if (q) {
    btn.disabled = true;
    btn.textContent = "Searching...";
    ws.send(JSON.stringify({ command: "search", data: { search: q } }));
  }
}

ws.onopen = () => {
  fetch("/status").then(res => res.json()).then(status => {
    for (const [id, job] of Object.entries(status)) {
      updateDownloadUI(id, job.filename, job.progress || 0, job.status);
    }
  });
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === "search_results") {
    const results = document.getElementById("results");
    const btn = document.getElementById("searchBtn");
    btn.disabled = false;
    btn.textContent = "Search";
    results.innerHTML = "";
    msg.results.forEach(game => {
      const div = document.createElement("div");
      div.className = "result-entry";

      const title = document.createElement("div");
      title.textContent = `${game.url} (${(game.size / 1024 / 1024).toFixed(2)} MB)`;

      const btn = document.createElement("button");
      btn.textContent = "Download";
      btn.onclick = () => {
        ws.send(JSON.stringify({ command: "download", data: { download: game.id } }));
      };

      div.appendChild(title);
      div.appendChild(btn);
      results.appendChild(div);
    });
  }

  if (msg.type === "queued") {
    console.log(msg.msg);
  }

  if (msg.type === "progress") {
    updateDownloadUI(msg.filename, msg.filename, msg.progress);
  }

  if (msg.type === "download_complete") {
    updateDownloadUI(msg.file, msg.file, 100, "completed");
  }

  if (msg.type === "download_error") {
    updateDownloadUI(msg.file || "Unknown", msg.file || "Unknown", 0, "error");
  }
};

document.getElementById("searchBtn").addEventListener("click", doSearch);
document.getElementById("searchBox").addEventListener("keydown", e => {
  if (e.key === "Enter") doSearch();
});
