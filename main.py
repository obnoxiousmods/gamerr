import os
import uuid
import httpx
import anyio
import re

from starlette.applications import Starlette
from starlette.routing import WebSocketRoute, Route, Mount
from starlette.endpoints import WebSocketEndpoint
from starlette.websockets import WebSocket
from starlette.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates
from starlette.requests import Request
from starlette.staticfiles import StaticFiles

JSON_URL = "https://tinfoil.ultranx.ru/tinfoil"
HEADERS = {"User-Agent": "Tinfoil"}
DOWNLOAD_DIR = "/1TB/switch/switchGames"

templates = Jinja2Templates(directory="templates")
download_limiter = anyio.CapacityLimiter(3)
downloads = {}  # in-memory job tracking

def sanitize_filename(name):
    return re.sub(r'[<>:"/\\\\|?*]', "_", name)

class GameDownloadApp:
    def __init__(self):
        self.app = Starlette(routes=self.get_routes())
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.app.state.app_instance = self

    def get_routes(self):
        return [
            Route("/", endpoint=self.homepage),
            WebSocketRoute("/ws", endpoint=DownloadSocket),
            Mount("/static", app=StaticFiles(directory="static"), name="static"),
        ]

    async def homepage(self, request: Request):
        return templates.TemplateResponse("index.html", {"request": request})

    @staticmethod
    async def fetch_game_json():
        async with httpx.AsyncClient() as client:
            res = await client.get(JSON_URL, headers=HEADERS)
            res.raise_for_status()
            return res.json()

    @staticmethod
    def extract_matches(json_data, search_term):
        matches = []
        for entry in json_data.get("files", []):
            url = entry.get("url", "")
            size = entry.get("size", 0)
            if search_term.lower() in url.lower():
                matches.append(
                    {
                        "url": url,
                        "size": size,
                        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, url)),
                    }
                )
        return matches

    async def download_file(self, url, doc_id, websocket: WebSocket = None):
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        filename = url.split("/")[-1].split("?")[0]
        filename = sanitize_filename(filename)
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        

        async with httpx.AsyncClient(follow_redirects=True) as client:
            async with client.stream("GET", url, headers=HEADERS) as response:
                total = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                last_percent = -1

                async with await anyio.open_file(filepath, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        await f.write(chunk)
                        await f.flush()
                        
                        downloaded += len(chunk)
                        if websocket and total:
                            percent = int((downloaded / total) * 100)
                            if percent > last_percent:
                                last_percent = percent
                                print(f"[{filename}] Progress: {percent}%")
                                if websocket.client_state.name == "CONNECTED":
                                    try:
                                        await websocket.send_json({
                                            "type": "progress",
                                            "progress": percent,
                                            "filename": filename
                                        })
                                    except Exception as e:
                                        print(f"Error sending progress: {e}")
                                        continue


        return filename


class DownloadSocket(WebSocketEndpoint):
    encoding = "json"

    async def on_connect(self, websocket: WebSocket):
        await websocket.accept()
        self.search_index = []
        self.app_instance = websocket.app.state.app_instance

    async def on_receive(self, websocket: WebSocket, data):
        command = data.get("command")
        payload = data.get("data", {})

        if command == "search":
            search_term = payload.get("search", "")
            json_data = await self.app_instance.fetch_game_json()
            matches = self.app_instance.extract_matches(json_data, search_term)
            self.search_index = matches
            await websocket.send_json({"type": "search_results", "results": matches})

        elif command == "download":
            game_id = payload.get("download")
            match = next((m for m in self.search_index if m["id"] == game_id), None)
            if not match:
                await websocket.send_json(
                    {"type": "download_error", "error": "Game not found."}
                )
                return

            doc_id = f"dl-{uuid.uuid4()}"
            url = match["url"]
            filename = url.split("/")[-1].split("?")[0]
            downloads[doc_id] = {
                "status": "queued",
                "filename": filename,
                "url": url,
            }

            await websocket.send_json(
                {"type": "queued", "msg": f"Queued for download: {filename}"}
            )

            async def queue_download():
                async with download_limiter:
                    try:
                        downloads[doc_id]["status"] = "downloading"
                        result = await self.app_instance.download_file(
                            url, doc_id, websocket
                        )
                        downloads[doc_id]["status"] = "completed"
                        downloads[doc_id]["file"] = result
                        await websocket.send_json(
                            {"type": "download_complete", "file": result}
                        )
                    except Exception as e:
                        downloads[doc_id]["status"] = "error"
                        downloads[doc_id]["error"] = str(e)
                        await websocket.send_json(
                            {"type": "download_error", "file": filename, "error": str(e)}
                        )

            async with anyio.create_task_group() as tg:
                tg.start_soon(queue_download)


app = GameDownloadApp().app
