const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);

function setSearchState(disabled, text = "Search") {
  const btn = document.getElementById("searchBtn");
  const box = document.getElementById("searchBox");
  btn.disabled = disabled;
  box.disabled = disabled;
  btn.textContent = text;
}

function doSearch() {
  const query = document.getElementById("searchBox").value.trim();
  const errorBox = document.getElementById("errorBox");
  if (!query) return;

  // Clear previous errors and results
  errorBox.style.display = "none";
  document.getElementById("results").innerHTML = "";

  setSearchState(true, "Searching...");
  ws.send(JSON.stringify({ command: "search", data: { search: query } }));
}

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  const errorBox = document.getElementById("errorBox");

  if (msg.type === "search_results") {
    const resultsDiv = document.getElementById("results");
    resultsDiv.innerHTML = "";

    if (msg.results.length === 0) {
      resultsDiv.textContent = "No results found.";
    }

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

    setSearchState(false);
  }

  if (msg.type === "download_error" || msg.type === "search_error") {
    errorBox.textContent = `Error: ${msg.error || "Search failed."}`;
    errorBox.style.display = "block";
    setSearchState(false);
  }

  if (msg.type === "progress") {
    const bar = document.getElementById("downloadProgress");
    bar.style.width = `${msg.progress}%`;
    bar.textContent = `${msg.progress}%`;
  }

  if (msg.type === "download_complete") {
    alert(`Download complete: ${msg.file}`);
  }
};

window.onload = () => {
  document.getElementById("searchBox").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.target.disabled) {
      doSearch();
    }
  });

  document.getElementById("searchBtn").addEventListener("click", () => {
    if (!document.getElementById("searchBtn").disabled) {
      doSearch();
    }
  });
};
