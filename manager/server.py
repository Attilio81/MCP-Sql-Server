# -*- coding: utf-8 -*-
"""FastAPI app — API routes + serve index.html."""
import threading
import webbrowser
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from manager import config_manager, connection_tester

app = FastAPI(title="SQL MCP Manager")
STATIC_DIR = Path(__file__).parent / "static"


# ------------------------------------------------------------------ #
#  Pydantic models                                                     #
# ------------------------------------------------------------------ #

class ServerEntry(BaseModel):
    name: str
    connection_string: str
    max_rows: Optional[int] = 100
    query_timeout: Optional[int] = 30
    pool_size: Optional[int] = 5
    pool_timeout: Optional[int] = 30
    allowed_schemas: Optional[str] = ""
    blacklist_tables: Optional[str] = ""
    log_level: Optional[str] = "INFO"


class TestRequest(BaseModel):
    connection_string: str


# ------------------------------------------------------------------ #
#  API routes                                                          #
# ------------------------------------------------------------------ #

@app.get("/api/servers")
def get_servers():
    return config_manager.list_servers()


@app.post("/api/servers", status_code=201)
def add_server(entry: ServerEntry):
    try:
        config_manager.add_server(entry.model_dump())
    except ValueError as exc:
        if "already exists" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@app.put("/api/servers/{name}")
def update_server(name: str, entry: ServerEntry):
    if entry.name != name:
        raise HTTPException(status_code=400, detail="Name in body must match URL path")
    try:
        config_manager.update_server(name, entry.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@app.delete("/api/servers/{name}")
def delete_server(name: str):
    try:
        config_manager.delete_server(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ok": True}


@app.post("/api/test")
def test_connection(req: TestRequest):
    return connection_tester.test_connection(req.connection_string)


# ------------------------------------------------------------------ #
#  Frontend                                                            #
# ------------------------------------------------------------------ #

@app.get("/")
def serve_frontend():
    return FileResponse(STATIC_DIR / "index.html")


# ------------------------------------------------------------------ #
#  Entry point                                                         #
# ------------------------------------------------------------------ #

def run():
    """Start server and auto-open browser."""
    def _open_browser():
        import time
        time.sleep(0.8)
        webbrowser.open("http://localhost:8090")

    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8090)


if __name__ == "__main__":
    run()
