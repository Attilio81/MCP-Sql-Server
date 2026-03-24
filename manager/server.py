# -*- coding: utf-8 -*-
"""FastAPI app — API routes + serve index.html."""
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

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

    @field_validator("name")
    @classmethod
    def name_no_url_unsafe(cls, v: str) -> str:
        import re
        if not v.strip():
            raise ValueError("name cannot be empty")
        if re.search(r'[/?#%]', v):
            raise ValueError("name cannot contain /, ?, #, or % characters")
        return v


class TestRequest(BaseModel):
    connection_string: str


# ------------------------------------------------------------------ #
#  API routes                                                          #
# ------------------------------------------------------------------ #

@app.get("/api/servers")
def get_servers():
    try:
        return config_manager.list_servers()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"ok": True}


@app.post("/api/test")
def test_connection(req: TestRequest):
    return connection_tester.test_connection(req.connection_string)


@app.post("/api/servers/{name}/register-claude-code")
def register_claude_code(name: str):
    # Find the entry
    try:
        servers = config_manager.list_servers()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    entry = next((s for s in servers if s["name"] == name), None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Server '{name}' not found")

    # Locate claude CLI (on Windows it may be claude.cmd)
    claude_exe = None
    for candidate in (("claude.cmd", "claude") if sys.platform == "win32" else ("claude",)):
        if shutil.which(candidate):
            claude_exe = candidate
            break
    if not claude_exe:
        return {"ok": False, "error": "Claude CLI non trovato. Installa Claude Code e verifica che 'claude' sia nel PATH."}

    # Build: claude mcp add <name> --scope user python -m mcp_sqlserver.server --connection-string "..." [opts]
    cmd = [claude_exe, "mcp", "add", name, "--scope", "user", "python",
           "-m", "mcp_sqlserver.server",
           "--connection-string", entry["connection_string"]]
    for field, flag in (("max_rows", "--max-rows"), ("query_timeout", "--query-timeout"),
                        ("pool_size", "--pool-size"), ("pool_timeout", "--pool-timeout"),
                        ("allowed_schemas", "--allowed-schemas"),
                        ("blacklist_tables", "--blacklist-tables"),
                        ("log_level", "--log-level")):
        val = entry.get(field)
        if val is not None and str(val).strip() not in ("", "INFO"):
            cmd.extend([flag, str(val)])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15,
            shell=(sys.platform == "win32"),
        )
        if result.returncode == 0:
            return {"ok": True, "output": result.stdout.strip() or f"'{name}' registrato su Claude Code."}
        else:
            err = (result.stderr or result.stdout).strip()
            return {"ok": False, "error": err or "Comando fallito senza messaggio."}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Timeout: Claude CLI non risponde."}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


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
