# SQL MCP Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local FastAPI web app at `manager/` that lets users add, edit, delete, and test SQL Server MCP connections stored in `claude_desktop_config.json`.

**Architecture:** FastAPI serves a REST API (5 endpoints) and a single `index.html` frontend. `config_manager.py` handles all file I/O with atomic writes. `connection_tester.py` wraps pyodbc. No build step — vanilla HTML/CSS/JS only.

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, pyodbc (already installed), vanilla HTML/CSS/JS

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `manager/__init__.py` | Empty — marks folder as Python package |
| Create | `manager/config_manager.py` | Detect config path, read/write/parse/serialize entries, atomic write |
| Create | `manager/connection_tester.py` | Single function: test connection string via pyodbc |
| Create | `manager/server.py` | FastAPI app, all API routes, serve index.html, entry point |
| Create | `manager/static/index.html` | Single-page UI — vanilla HTML/CSS/JS |
| Modify | `pyproject.toml` | Add `[project.optional-dependencies] manager` group |
| Create | `tests/test_config_manager.py` | Unit tests — no DB, uses tmp_path |
| Create | `tests/test_connection_tester.py` | Unit tests — mocks pyodbc |
| Create | `tests/test_api.py` | API tests via FastAPI TestClient — mocks config_manager |

---

## Task 1: Scaffold — package structure + pyproject.toml

**Files:**
- Create: `manager/__init__.py`
- Create: `manager/static/.gitkeep`
- Modify: `pyproject.toml`

- [ ] **Step 1: Create package files**

```bash
mkdir -p manager/static
touch manager/__init__.py
touch manager/static/.gitkeep
```

- [ ] **Step 2: Add optional dependencies to pyproject.toml**

Open `pyproject.toml` and add this block after the `[project]` section:

```toml
[project.optional-dependencies]
manager = [
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
]
```

- [ ] **Step 3: Install manager dependencies**

```bash
pip install -e ".[manager]"
```

Expected: installs fastapi and uvicorn without errors.

- [ ] **Step 4: Commit**

```bash
git add manager/__init__.py manager/static/.gitkeep pyproject.toml
git commit -m "feat: scaffold manager package with optional deps"
```

---

## Task 2: config_manager.py (TDD)

**Files:**
- Create: `manager/config_manager.py`
- Create: `tests/test_config_manager.py`

The Claude Desktop config stores each MCP server as:
```json
{
  "mcpServers": {
    "db-vendite": {
      "command": "python",
      "args": ["-m", "mcp_sqlserver.server", "--connection-string", "...", "--max-rows", "100"]
    }
  }
}
```

`config_manager.py` must detect this project's entries by checking `"mcp_sqlserver.server" in args` (array membership, not substring), parse args into a flat dict, and write back atomically.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config_manager.py`:

```python
import json
import os
import pytest
from pathlib import Path
from manager.config_manager import (
    detect_config_path,
    read_config,
    list_servers,
    add_server,
    update_server,
    delete_server,
    _parse_entry,
    _serialize_entry,
)

SAMPLE_ENTRY = {
    "name": "db-test",
    "connection_string": "Driver={ODBC Driver 17 for SQL Server};Server=srv1;Database=DB;Trusted_Connection=yes",
    "max_rows": 100,
    "query_timeout": 30,
    "pool_size": 5,
    "pool_timeout": 30,
    "allowed_schemas": "dbo",
    "blacklist_tables": "sys_*",
    "log_level": "INFO",
}


def test_detect_config_path_returns_path():
    path = detect_config_path()
    assert isinstance(path, Path)
    assert path.name == "claude_desktop_config.json"


def test_read_config_returns_empty_when_missing(tmp_path):
    result = read_config(tmp_path / "nonexistent.json")
    assert result == {"mcpServers": {}}


def test_read_config_returns_parsed_json(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"mcpServers": {}}', encoding="utf-8")
    assert read_config(cfg) == {"mcpServers": {}}


def test_serialize_and_parse_roundtrip():
    serialized = _serialize_entry(SAMPLE_ENTRY)
    assert serialized["command"] == "python"
    assert "mcp_sqlserver.server" in serialized["args"]
    parsed = _parse_entry("db-test", serialized["args"])
    assert parsed["connection_string"] == SAMPLE_ENTRY["connection_string"]
    assert parsed["max_rows"] == 100


def test_add_server_creates_entry(tmp_path):
    cfg = tmp_path / "config.json"
    add_server(SAMPLE_ENTRY, path=cfg)
    config = json.loads(cfg.read_text())
    assert "db-test" in config["mcpServers"]
    assert "mcp_sqlserver.server" in config["mcpServers"]["db-test"]["args"]


def test_add_server_raises_on_duplicate(tmp_path):
    cfg = tmp_path / "config.json"
    add_server(SAMPLE_ENTRY, path=cfg)
    with pytest.raises(ValueError, match="already exists"):
        add_server(SAMPLE_ENTRY, path=cfg)


def test_add_server_preserves_other_entries(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "mcpServers": {"other-tool": {"command": "node", "args": ["server.js"]}}
    }), encoding="utf-8")
    add_server(SAMPLE_ENTRY, path=cfg)
    config = json.loads(cfg.read_text())
    assert "other-tool" in config["mcpServers"]
    assert "db-test" in config["mcpServers"]


def test_update_server_modifies_entry(tmp_path):
    cfg = tmp_path / "config.json"
    add_server(SAMPLE_ENTRY, path=cfg)
    update_server("db-test", {**SAMPLE_ENTRY, "max_rows": 200}, path=cfg)
    servers = list_servers(path=cfg)
    assert servers[0]["max_rows"] == 200


def test_update_server_raises_on_missing(tmp_path):
    cfg = tmp_path / "config.json"
    with pytest.raises(KeyError):
        update_server("nonexistent", SAMPLE_ENTRY, path=cfg)


def test_delete_server_removes_entry(tmp_path):
    cfg = tmp_path / "config.json"
    add_server(SAMPLE_ENTRY, path=cfg)
    delete_server("db-test", path=cfg)
    assert list_servers(path=cfg) == []


def test_delete_server_raises_on_missing(tmp_path):
    cfg = tmp_path / "config.json"
    with pytest.raises(KeyError):
        delete_server("nonexistent", path=cfg)


def test_list_servers_excludes_non_sqlserver_entries(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "mcpServers": {"other-tool": {"command": "node", "args": ["server.js"]}}
    }), encoding="utf-8")
    assert list_servers(path=cfg) == []


def test_write_is_atomic(tmp_path, monkeypatch):
    """Verify original file is untouched if os.replace raises."""
    cfg = tmp_path / "config.json"
    add_server(SAMPLE_ENTRY, path=cfg)
    original = cfg.read_text()

    def failing_replace(src, dst):
        raise OSError("simulated disk full")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(OSError):
        add_server({**SAMPLE_ENTRY, "name": "db-test2"}, path=cfg)

    assert cfg.read_text() == original
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config_manager.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `config_manager` does not exist yet.

- [ ] **Step 3: Implement config_manager.py**

Create `manager/config_manager.py`:

```python
# -*- coding: utf-8 -*-
"""
Read/write claude_desktop_config.json for mcp_sqlserver entries.
"""
import json
import os
import sys
from pathlib import Path
from typing import Optional


def detect_config_path() -> Path:
    """Return platform-specific path to claude_desktop_config.json."""
    if sys.platform == "win32":
        return Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def read_config(path: Path) -> dict:
    """Return parsed config dict; returns {'mcpServers': {}} if file missing."""
    if not path.exists():
        return {"mcpServers": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_config(path: Path, config: dict) -> None:
    """Write config atomically via a .tmp file + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _serialize_entry(entry: dict) -> dict:
    """Convert data-model dict → Claude Desktop config format (command + args)."""
    args = ["-m", "mcp_sqlserver.server"]
    field_to_flag = {
        "connection_string": "--connection-string",
        "max_rows": "--max-rows",
        "query_timeout": "--query-timeout",
        "pool_size": "--pool-size",
        "pool_timeout": "--pool-timeout",
        "allowed_schemas": "--allowed-schemas",
        "blacklist_tables": "--blacklist-tables",
        "log_level": "--log-level",
    }
    for field, flag in field_to_flag.items():
        val = entry.get(field)
        if val is not None and str(val).strip() != "":
            args.extend([flag, str(val)])
    return {"command": "python", "args": args}


def _parse_entry(name: str, args: list) -> dict:
    """Convert Claude Desktop args array → data-model dict."""
    entry: dict = {"name": name}
    i = 0
    while i < len(args):
        if args[i].startswith("--") and i + 1 < len(args):
            key = args[i][2:].replace("-", "_")
            entry[key] = args[i + 1]
            i += 2
        else:
            i += 1
    for int_field in ("max_rows", "query_timeout", "pool_size", "pool_timeout"):
        if int_field in entry:
            try:
                entry[int_field] = int(entry[int_field])
            except (ValueError, TypeError):
                pass
    return entry


def list_servers(path: Optional[Path] = None) -> list:
    """Return all mcp_sqlserver entries as data-model dicts."""
    if path is None:
        path = detect_config_path()
    config = read_config(path)
    result = []
    for name, entry in config.get("mcpServers", {}).items():
        args = entry.get("args", [])
        if "mcp_sqlserver.server" in args:
            result.append(_parse_entry(name, args))
    return result


def add_server(entry: dict, path: Optional[Path] = None) -> None:
    """Add a new server entry. Raises ValueError if name already exists."""
    if path is None:
        path = detect_config_path()
    config = read_config(path)
    name = entry["name"]
    if name in config.get("mcpServers", {}):
        raise ValueError(f"Server '{name}' already exists")
    config.setdefault("mcpServers", {})[name] = _serialize_entry(entry)
    _write_config(path, config)


def update_server(name: str, entry: dict, path: Optional[Path] = None) -> None:
    """Update an existing server entry. Raises KeyError if not found."""
    if path is None:
        path = detect_config_path()
    config = read_config(path)
    if name not in config.get("mcpServers", {}):
        raise KeyError(f"Server '{name}' not found")
    config["mcpServers"][name] = _serialize_entry(entry)
    _write_config(path, config)


def delete_server(name: str, path: Optional[Path] = None) -> None:
    """Delete a server entry. Raises KeyError if not found."""
    if path is None:
        path = detect_config_path()
    config = read_config(path)
    if name not in config.get("mcpServers", {}):
        raise KeyError(f"Server '{name}' not found")
    del config["mcpServers"][name]
    _write_config(path, config)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config_manager.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add manager/config_manager.py tests/test_config_manager.py
git commit -m "feat: add config_manager with atomic read/write for claude_desktop_config.json"
```

---

## Task 3: connection_tester.py (TDD)

**Files:**
- Create: `manager/connection_tester.py`
- Create: `tests/test_connection_tester.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_connection_tester.py`:

```python
from unittest.mock import patch, MagicMock
from manager.connection_tester import test_connection


def test_successful_connection():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (1,)
    with patch("pyodbc.connect", return_value=mock_conn):
        result = test_connection("Driver=...;Server=localhost")
    assert result["ok"] is True
    assert result["error"] is None


def test_failed_connection():
    with patch("pyodbc.connect", side_effect=Exception("Connection refused")):
        result = test_connection("Driver=...;Server=bad-host")
    assert result["ok"] is False
    assert "Connection refused" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_connection_tester.py -v
```

Expected: `ImportError` — module does not exist yet.

- [ ] **Step 3: Implement connection_tester.py**

Create `manager/connection_tester.py`:

```python
# -*- coding: utf-8 -*-
"""Test a SQL Server connection string via pyodbc."""
import pyodbc


def test_connection(connection_string: str) -> dict:
    """
    Attempt to connect and run SELECT 1.
    Returns {"ok": True, "error": None} on success,
    or {"ok": False, "error": "<message>"} on failure.
    """
    try:
        conn = pyodbc.connect(connection_string, timeout=5)
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return {"ok": True, "error": None}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_connection_tester.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add manager/connection_tester.py tests/test_connection_tester.py
git commit -m "feat: add connection_tester wrapping pyodbc"
```

---

## Task 4: FastAPI server — API endpoints (TDD)

**Files:**
- Create: `manager/server.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api.py`:

```python
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from manager.server import app

client = TestClient(app)

SAMPLE_ENTRY = {
    "name": "db-test",
    "connection_string": "Driver={ODBC Driver 17 for SQL Server};Server=srv1;Database=DB;Trusted_Connection=yes",
    "max_rows": 100,
    "query_timeout": 30,
    "pool_size": 5,
    "pool_timeout": 30,
    "allowed_schemas": "dbo",
    "blacklist_tables": "",
    "log_level": "INFO",
}


def test_get_servers_returns_list():
    with patch("manager.server.config_manager.list_servers", return_value=[]):
        response = client.get("/api/servers")
    assert response.status_code == 200
    assert response.json() == []


def test_post_server_success():
    with patch("manager.server.config_manager.add_server") as mock_add:
        response = client.post("/api/servers", json=SAMPLE_ENTRY)
    assert response.status_code == 201
    mock_add.assert_called_once()


def test_post_server_duplicate_returns_409():
    with patch("manager.server.config_manager.add_server", side_effect=ValueError("already exists")):
        response = client.post("/api/servers", json=SAMPLE_ENTRY)
    assert response.status_code == 409


def test_put_server_success():
    with patch("manager.server.config_manager.update_server") as mock_update:
        response = client.put("/api/servers/db-test", json=SAMPLE_ENTRY)
    assert response.status_code == 200
    mock_update.assert_called_once()


def test_put_server_not_found_returns_404():
    with patch("manager.server.config_manager.update_server", side_effect=KeyError("not found")):
        response = client.put("/api/servers/db-test", json=SAMPLE_ENTRY)
    assert response.status_code == 404


def test_delete_server_success():
    with patch("manager.server.config_manager.delete_server") as mock_delete:
        response = client.delete("/api/servers/db-test")
    assert response.status_code == 200
    mock_delete.assert_called_once_with("db-test")


def test_delete_server_not_found_returns_404():
    with patch("manager.server.config_manager.delete_server", side_effect=KeyError("not found")):
        response = client.delete("/api/servers/db-test")
    assert response.status_code == 404


def test_post_test_success():
    with patch("manager.server.connection_tester.test_connection",
               return_value={"ok": True, "error": None}):
        response = client.post("/api/test", json={"connection_string": "..."})
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_post_test_failure():
    with patch("manager.server.connection_tester.test_connection",
               return_value={"ok": False, "error": "timeout"}):
        response = client.post("/api/test", json={"connection_string": "..."})
    assert response.status_code == 200
    assert response.json()["ok"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_api.py -v
```

Expected: `ImportError` — `manager.server` does not exist yet.

- [ ] **Step 3: Implement server.py**

Create `manager/server.py`:

```python
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
        raise HTTPException(status_code=409, detail=str(exc))
    return {"ok": True}


@app.put("/api/servers/{name}")
def update_server(name: str, entry: ServerEntry):
    try:
        config_manager.update_server(name, entry.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_api.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
pytest tests/ -v
```

Expected: all tests PASS (including pre-existing `test_security_validator.py`).

- [ ] **Step 6: Commit**

```bash
git add manager/server.py tests/test_api.py
git commit -m "feat: add FastAPI server with CRUD and test-connection endpoints"
```

---

## Task 5: Frontend — index.html

**Files:**
- Create: `manager/static/index.html`

No unit tests — this is a vanilla HTML/JS file. Manual testing steps are provided below.

- [ ] **Step 1: Create manager/static/index.html**

Create `manager/static/index.html` with the following content:

```html
<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SQL MCP Manager</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8fafc; color: #1e293b; padding: 32px 24px; }
    .wrap { max-width: 860px; margin: 0 auto; }

    /* Header */
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
    .title { font-size: 1.5rem; font-weight: 700; }
    .title span { color: #6c63ff; }
    .btn-primary { background: #6c63ff; color: #fff; border: none; padding: 9px 18px; border-radius: 8px; font-size: 0.9rem; font-weight: 600; cursor: pointer; }
    .btn-primary:hover { background: #5a52e0; }

    /* Error banner */
    .banner { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; border-radius: 8px; padding: 12px 16px; margin-bottom: 18px; display: none; }
    .banner.visible { display: block; }

    /* Server list */
    .section-label { font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #94a3b8; margin-bottom: 10px; }
    .server-list { display: flex; flex-direction: column; gap: 10px; }
    .card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 20px; display: flex; align-items: center; gap: 16px; }
    .dot { width: 11px; height: 11px; border-radius: 50%; flex-shrink: 0; background: #94a3b8; }
    .dot.online { background: #22c55e; box-shadow: 0 0 0 3px #22c55e33; }
    .dot.offline { background: #ef4444; box-shadow: 0 0 0 3px #ef444433; }
    .card-info { flex: 1; min-width: 0; }
    .card-name { font-weight: 700; font-size: 1rem; }
    .card-meta { font-size: 0.82rem; color: #64748b; margin-top: 3px; display: flex; gap: 10px; flex-wrap: wrap; }
    .tag { background: #f1f5f9; border-radius: 5px; padding: 2px 8px; font-size: 0.75rem; color: #475569; font-weight: 500; }
    .tag.purple { background: #ede9fe; color: #6c63ff; }
    .card-err { color: #ef4444; font-size: 0.8rem; }
    .card-actions { display: flex; gap: 6px; flex-shrink: 0; }
    .btn-sm { border: 1px solid #e2e8f0; background: #fff; border-radius: 7px; padding: 6px 10px; font-size: 0.8rem; cursor: pointer; color: #475569; }
    .btn-sm:hover { background: #f8fafc; }
    .btn-sm.purple { border-color: #c4b5fd; color: #6c63ff; }
    .btn-sm.purple:hover { background: #ede9fe; }
    .btn-sm.red:hover { background: #fef2f2; color: #ef4444; border-color: #fecaca; }

    /* Form panel */
    .form-panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px; margin-top: 20px; display: none; }
    .form-panel.visible { display: block; }
    .form-title { font-size: 1rem; font-weight: 700; margin-bottom: 18px; }
    .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    .form-full { grid-column: 1 / -1; }
    .form-group label { display: block; font-size: 0.75rem; font-weight: 600; color: #64748b; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.04em; }
    .form-group input { width: 100%; padding: 9px 12px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 0.88rem; }
    .form-group input:focus { outline: none; border-color: #6c63ff; box-shadow: 0 0 0 3px #6c63ff22; }
    .form-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; padding-top: 16px; border-top: 1px solid #f1f5f9; align-items: center; }
    .btn-cancel { background: #f8fafc; color: #64748b; border: 1px solid #e2e8f0; padding: 9px 18px; border-radius: 8px; font-weight: 600; font-size: 0.88rem; cursor: pointer; }
    .btn-test { background: #ede9fe; color: #6c63ff; border: 1px solid #c4b5fd; padding: 9px 14px; border-radius: 8px; font-weight: 600; font-size: 0.88rem; cursor: pointer; }
    .btn-save { background: #6c63ff; color: #fff; border: none; padding: 9px 20px; border-radius: 8px; font-weight: 600; font-size: 0.88rem; cursor: pointer; }
    .test-result { font-size: 0.82rem; margin-right: auto; }
    .test-result.ok { color: #16a34a; }
    .test-result.fail { color: #ef4444; }
  </style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div class="title">SQL MCP <span>Manager</span></div>
    <button class="btn-primary" onclick="openForm()">＋ Nuova Connessione</button>
  </div>

  <div class="banner" id="banner"></div>

  <div class="section-label" id="list-label">Caricamento...</div>
  <div class="server-list" id="server-list"></div>

  <div class="form-panel" id="form-panel">
    <div class="form-title" id="form-title">Nuova connessione</div>
    <input type="hidden" id="edit-name">
    <div class="form-grid">
      <div class="form-group">
        <label>Nome MCP Server *</label>
        <input type="text" id="f-name" placeholder="es. db-vendite">
      </div>
      <div class="form-group">
        <label>Max Righe</label>
        <input type="number" id="f-max-rows" placeholder="100">
      </div>
      <div class="form-group form-full">
        <label>Connection String *</label>
        <input type="text" id="f-conn" placeholder="Driver={ODBC Driver 17 for SQL Server};Server=...;Database=...;Trusted_Connection=yes">
      </div>
      <div class="form-group">
        <label>Schema Consentiti</label>
        <input type="text" id="f-schemas" placeholder="dbo, sales">
      </div>
      <div class="form-group">
        <label>Tabelle Blacklist</label>
        <input type="text" id="f-blacklist" placeholder="sys_*, *_audit">
      </div>
      <div class="form-group">
        <label>Query Timeout (s)</label>
        <input type="number" id="f-query-timeout" placeholder="30">
      </div>
      <div class="form-group">
        <label>Pool Size</label>
        <input type="number" id="f-pool-size" placeholder="5">
      </div>
      <div class="form-group">
        <label>Pool Timeout (s)</label>
        <input type="number" id="f-pool-timeout" placeholder="30">
      </div>
    </div>
    <div class="form-actions">
      <span class="test-result" id="test-result"></span>
      <button class="btn-cancel" onclick="closeForm()">Annulla</button>
      <button class="btn-test" onclick="testForm()">⚡ Testa</button>
      <button class="btn-save" onclick="saveForm()">Salva</button>
    </div>
  </div>
</div>

<script>
  let servers = [];

  async function loadServers() {
    try {
      const res = await fetch('/api/servers');
      if (!res.ok) throw new Error(await res.text());
      servers = await res.json();
      renderList();
      checkAllStatus();
    } catch (e) {
      showBanner('Errore caricamento: ' + e.message);
    }
  }

  function renderList() {
    const el = document.getElementById('server-list');
    const label = document.getElementById('list-label');
    label.textContent = `Connessioni configurate — ${servers.length}`;
    if (servers.length === 0) {
      el.innerHTML = '<p style="color:#94a3b8;padding:16px 0">Nessuna connessione configurata.</p>';
      return;
    }
    el.innerHTML = servers.map((s, i) => `
      <div class="card" id="card-${i}">
        <div class="dot" id="dot-${i}" title="Verifica in corso..."></div>
        <div class="card-info">
          <div class="card-name">${esc(s.name)}</div>
          <div class="card-meta">
            <span>${connLabel(s.connection_string)}</span>
            ${s.allowed_schemas ? `<span class="tag purple">schema: ${esc(s.allowed_schemas)}</span>` : ''}
            ${s.max_rows ? `<span class="tag">max ${s.max_rows} righe</span>` : ''}
            ${s.query_timeout ? `<span class="tag">timeout ${s.query_timeout}s</span>` : ''}
            <span id="err-${i}"></span>
          </div>
        </div>
        <div class="card-actions">
          <button class="btn-sm purple" onclick="testCard(${i})">⚡</button>
          <button class="btn-sm" onclick="editCard(${i})">✏️</button>
          <button class="btn-sm red" onclick="deleteCard(${i})">🗑</button>
        </div>
      </div>`).join('');
  }

  function connLabel(cs) {
    const srv = cs.match(/Server=([^;]+)/i)?.[1] || '';
    const db  = cs.match(/Database=([^;]+)/i)?.[1] || '';
    return srv && db ? `🖥 ${esc(srv)} › ${esc(db)}` : esc(cs.substring(0, 40)) + '…';
  }

  function esc(s) {
    return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  async function checkAllStatus() {
    await Promise.all(servers.map((s, i) => checkStatus(i, s.connection_string)));
  }

  async function checkStatus(i, cs) {
    try {
      const res = await fetch('/api/test', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({connection_string: cs})
      });
      const data = await res.json();
      const dot = document.getElementById('dot-' + i);
      const err = document.getElementById('err-' + i);
      if (!dot) return;
      if (data.ok) {
        dot.className = 'dot online';
        dot.title = 'Connesso';
      } else {
        dot.className = 'dot offline';
        dot.title = data.error || 'Errore';
        if (err) err.className = 'card-err';
        if (err) err.textContent = '✗ ' + (data.error || 'Connessione fallita');
      }
    } catch (_) {}
  }

  async function testCard(i) {
    const dot = document.getElementById('dot-' + i);
    if (dot) { dot.className = 'dot'; dot.title = 'Verifica...'; }
    await checkStatus(i, servers[i].connection_string);
  }

  function editCard(i) {
    const s = servers[i];
    document.getElementById('edit-name').value = s.name;
    document.getElementById('form-title').textContent = `Modifica: ${s.name}`;
    document.getElementById('f-name').value = s.name;
    document.getElementById('f-name').disabled = true;
    document.getElementById('f-conn').value = s.connection_string || '';
    document.getElementById('f-max-rows').value = s.max_rows || '';
    document.getElementById('f-schemas').value = s.allowed_schemas || '';
    document.getElementById('f-blacklist').value = s.blacklist_tables || '';
    document.getElementById('f-query-timeout').value = s.query_timeout || '';
    document.getElementById('f-pool-size').value = s.pool_size || '';
    document.getElementById('f-pool-timeout').value = s.pool_timeout || '';
    document.getElementById('test-result').textContent = '';
    document.getElementById('form-panel').classList.add('visible');
  }

  async function deleteCard(i) {
    if (!confirm(`Eliminare la connessione "${servers[i].name}"?`)) return;
    try {
      const res = await fetch(`/api/servers/${encodeURIComponent(servers[i].name)}`, {method: 'DELETE'});
      if (!res.ok) throw new Error((await res.json()).detail);
      await loadServers();
    } catch (e) {
      showBanner('Errore eliminazione: ' + e.message);
    }
  }

  function openForm() {
    document.getElementById('edit-name').value = '';
    document.getElementById('form-title').textContent = 'Nuova connessione';
    document.getElementById('f-name').value = '';
    document.getElementById('f-name').disabled = false;
    ['f-conn','f-max-rows','f-schemas','f-blacklist','f-query-timeout','f-pool-size','f-pool-timeout']
      .forEach(id => document.getElementById(id).value = '');
    document.getElementById('test-result').textContent = '';
    document.getElementById('form-panel').classList.add('visible');
  }

  function closeForm() {
    document.getElementById('form-panel').classList.remove('visible');
  }

  async function testForm() {
    const cs = document.getElementById('f-conn').value.trim();
    if (!cs) { alert('Inserisci una connection string.'); return; }
    const el = document.getElementById('test-result');
    el.textContent = '⏳ Test in corso...';
    el.className = 'test-result';
    try {
      const res = await fetch('/api/test', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({connection_string: cs})
      });
      const data = await res.json();
      if (data.ok) {
        el.textContent = '✅ Connessione OK';
        el.className = 'test-result ok';
      } else {
        el.textContent = '❌ ' + (data.error || 'Errore');
        el.className = 'test-result fail';
      }
    } catch (e) {
      el.textContent = '❌ ' + e.message;
      el.className = 'test-result fail';
    }
  }

  async function saveForm() {
    const editName = document.getElementById('edit-name').value;
    const body = {
      name: document.getElementById('f-name').value.trim() || editName,
      connection_string: document.getElementById('f-conn').value.trim(),
      max_rows: parseInt(document.getElementById('f-max-rows').value) || 100,
      query_timeout: parseInt(document.getElementById('f-query-timeout').value) || 30,
      pool_size: parseInt(document.getElementById('f-pool-size').value) || 5,
      pool_timeout: parseInt(document.getElementById('f-pool-timeout').value) || 30,
      allowed_schemas: document.getElementById('f-schemas').value.trim(),
      blacklist_tables: document.getElementById('f-blacklist').value.trim(),
      log_level: 'INFO',
    };
    if (!body.name || !body.connection_string) {
      alert('Nome e Connection String sono obbligatori.');
      return;
    }
    try {
      const method = editName ? 'PUT' : 'POST';
      const url = editName ? `/api/servers/${encodeURIComponent(editName)}` : '/api/servers';
      const res = await fetch(url, {
        method,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error((await res.json()).detail);
      closeForm();
      await loadServers();
    } catch (e) {
      showBanner('Errore salvataggio: ' + e.message);
    }
  }

  function showBanner(msg) {
    const el = document.getElementById('banner');
    el.textContent = msg;
    el.classList.add('visible');
    setTimeout(() => el.classList.remove('visible'), 6000);
  }

  loadServers();
</script>
</body>
</html>
```

- [ ] **Step 2: Start the server and verify manually**

```bash
python -m manager.server
```

Expected: browser opens at `http://localhost:8090`, page loads, shows "Nessuna connessione configurata." if the config is empty.

- [ ] **Step 3: Manual smoke test — add a connection**

In the browser:
1. Click "Nuova Connessione"
2. Fill in Name: `db-test`, Connection String: `Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=test;Trusted_Connection=yes`
3. Click "Testa" — should show ✅ or ❌ depending on whether the server exists
4. Click "Salva" — card should appear in the list
5. Click "✏️" on the card — form should populate with existing values
6. Click "🗑" on the card — confirm dialog, card should disappear

- [ ] **Step 4: Verify config file was updated**

Open the Claude Desktop config file at `%APPDATA%\Claude\claude_desktop_config.json` (Windows) and confirm the entry was added/removed correctly.

- [ ] **Step 5: Commit**

```bash
git add manager/static/index.html
git commit -m "feat: add single-page management UI (vanilla HTML/CSS/JS)"
```

---

## Task 6: Final integration check + .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add .superpowers/ to .gitignore if not already present**

```bash
grep -q ".superpowers" .gitignore || echo ".superpowers/" >> .gitignore
```

- [ ] **Step 2: Run the full test suite one last time**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 3: Verify package entry point works**

```bash
pip install -e ".[manager]"
python -m manager.server --help 2>&1 || true
```

Expected: server starts (or shows uvicorn output). Stop with Ctrl+C.

- [ ] **Step 4: Final commit**

```bash
git add .gitignore
git commit -m "feat: SQL MCP Manager — complete implementation"
```

---

## Quick Reference

```bash
# Install
pip install -e ".[manager]"

# Run
python -m manager.server
# → http://localhost:8090

# Tests only
pytest tests/test_config_manager.py tests/test_connection_tester.py tests/test_api.py -v
```
