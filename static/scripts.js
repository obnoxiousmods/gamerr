const ws = new WebSocket(`ws://${location.host}/ws`);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === "search_results") {
    const resultsDiv = document.getElementById("results");
    resultsDiv.innerHTML = "";
    msg.results.forEach(game => {
      const div = document.createElement("div");
      div.className = "result field-row-stacked";
  
      const label = document.createElement("label");
      const sizeMB = (game.size / 1024 / 1024).toFixed(2);
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
    alert(`Download failed: ${msg.error}`);
  }
};

window.onload = () => {
  document.getElementById("searchBox").addEventListener("keydown", e => {
    if (e.key === "Enter") {
      ws.send(JSON.stringify({ command: "search", data: { search: e.target.value } }));
    }
  });
};
