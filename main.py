import os
import uuid
import httpx
from aiocouch import CouchDB, NotFoundError
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute, Route, Mount
from starlette.endpoints import WebSocketEndpoint
from starlette.websockets import WebSocket
from starlette.responses import HTMLResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates
from starlette.requests import Request
from starlette.staticfiles import StaticFiles

COUCH_SERVER = "http://127.0.0.1:5984"
COUCH_USER = "admin"
COUCH_PASS = "EpicPassword123!"
DB_NAME = "game_downloads"
JSON_URL = "https://tinfoil.ultranx.ru/tinfoil"
HEADERS = {"User-Agent": "Tinfoil"}
DOWNLOAD_DIR = "/10TB/qbt/switch/webappDownloads"

templates = Jinja2Templates(directory="templates")

class GameDownloadApp:
    def __init__(self):
        self.app = Starlette(routes=self.get_routes())
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=['*'],
            allow_methods=['*'],
            allow_headers=['*']
        )
        self.app.state.app_instance = self

    def get_routes(self):
        return [
            Route("/", endpoint=self.homepage),
            WebSocketRoute("/ws", endpoint=DownloadSocket),
            Mount("/static", app=StaticFiles(directory="static"), name="static")
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
                matches.append({
                    "url": url,
                    "size": size,
                    "id": str(uuid.uuid5(uuid.NAMESPACE_URL, url))
                })
        return matches

    async def download_file(self, url, doc_id, websocket: WebSocket = None):
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        filename = url.split("/")[-1].split("?")[0]
        filepath = os.path.join(DOWNLOAD_DIR, filename)

        async with httpx.AsyncClient(follow_redirects=True) as client:
            async with client.stream("GET", url, headers=HEADERS) as response:
                total = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                with open(filepath, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
                        downloaded += len(chunk)
                        if websocket and total:
                            percent = int((downloaded / total) * 100)
                            await websocket.send_json({"type": "progress", "progress": percent})
        return filename

    async def save_doc(self, doc_id, data):
        async with CouchDB(server=COUCH_SERVER, user=COUCH_USER, password=COUCH_PASS) as couch:
            db = await couch[DB_NAME]
            try:
                doc = await db[doc_id]
                doc.update(data)
            except NotFoundError:
                doc = await db.create(doc_id, data=data)
            await doc.save()

    async def get_all_docs(self):
        async with CouchDB(server=COUCH_SERVER, user=COUCH_USER, password=COUCH_PASS) as couch:
            db = await couch[DB_NAME]
            return [doc async for doc in db.values()]

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
            if match:
                doc_id = f"dl-{uuid.uuid4()}"
                url = match["url"]
                await self.app_instance.save_doc(doc_id, {"status": "started", "urls": [url]})
                try:
                    await self.app_instance.save_doc(doc_id, {"status": "downloading", "current": url})
                    filename = await self.app_instance.download_file(url, doc_id, websocket)
                    await self.app_instance.save_doc(doc_id, {"status": "completed", "file": filename})
                    await websocket.send_json({"type": "download_complete", "file": filename})
                except Exception as e:
                    await self.app_instance.save_doc(doc_id, {"status": "error", "error": str(e)})
                    await websocket.send_json({"type": "download_error", "error": str(e)})

app = GameDownloadApp().app
