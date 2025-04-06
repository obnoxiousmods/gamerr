const ws = new WebSocket(`ws://${location.host}/ws`);

function doSearch() {
  const query = document.getElementById("searchBox").value.trim();
  if (!query) return;
  ws.send(JSON.stringify({ command: "search", data: { search: query } }));
  document.getElementById("errorBox").style.display = "none";
}

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === "search_results") {
    const resultsDiv = document.getElementById("results");
    resultsDiv.innerHTML = "";
    msg.results.forEach(game => {
      const div = document.createElement("div");
      div.className = "result field-row-stacked";

      const sizeMB = (game.size / 1024 / 1024).toFixed(2);
      const label = document.createElement("label");
      label.textContent = `${game.url} (${sizeMB} MB)`;

      const btn = document.createElement("button");
      btn.textContent = "Download";
      btn.onclick = () => ws.send(JSON.stringify({ command: "download", data: { download: game.id } }));

      div.appendChild(label);
      div.appendChild(btn);
      resultsDiv.appendChild(div);
    });
  }

  if (msg.type === "progress") {
    const bar = document.getElementById("downloadProgress");
    bar.style.width = `${msg.progress}%`;
    bar.textContent = `${msg.progress}%`;
  }

  if (msg.type === "download_complete") {
    alert(`Download complete: ${msg.file}`);
  }

  if (msg.type === "download_error") {
    const errorBox = document.getElementById("errorBox");
    errorBox.textContent = `Error: ${msg.error}`;
    errorBox.style.display = "block";
  }
};

window.onload = () => {
  document.getElementById("searchBox").addEventListener("keydown", e => {
    if (e.key === "Enter") doSearch();
  });

  document.getElementById("searchBtn").addEventListener("click", () => {
    doSearch();
  });
};
