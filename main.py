from __future__ import annotations

import os
import socket
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.deps import STATIC_DIR, FILE_SERVER_PORT, config_manager
from routers import papers, branches, chat, config as config_router

app = FastAPI(title="论文阅读助手")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def start_file_server():
    from core.deps import PAPERS_DIR, FILE_SERVER_URL

    papers_path = PAPERS_DIR.resolve()

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    os.chdir(papers_path)
    server = HTTPServer(("0.0.0.0", FILE_SERVER_PORT), QuietHandler)
    local_ip = get_local_ip()

    import core.deps

    core.deps.FILE_SERVER_URL = f"http://{local_ip}:{FILE_SERVER_PORT}"

    print(f"File server started at {core.deps.FILE_SERVER_URL}")
    server.serve_forever()


@app.on_event("startup")
async def startup_event():
    thread = threading.Thread(target=start_file_server, daemon=True)
    thread.start()


app.include_router(papers.router)
app.include_router(branches.router)
app.include_router(chat.router)
app.include_router(config_router.router)

branches.setup_view_route(app)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/api/config/client")
async def get_client_config():
    return config_manager.get_client_config()


@app.get("/api/file-server-url")
async def get_file_server_url():
    from core.deps import FILE_SERVER_URL

    return {"url": FILE_SERVER_URL}


@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn

    server_config = config_manager.get_server_config()
    host = server_config.get("host", "0.0.0.0")
    port = server_config.get("port", 8000)
    uvicorn.run(app, host=host, port=port)
