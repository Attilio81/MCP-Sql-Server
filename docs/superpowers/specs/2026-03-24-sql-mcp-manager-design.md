# SQL MCP Manager — Design Spec

**Date:** 2026-03-24
**Status:** Approved by user

---

## Overview

A local web-based management UI integrated into the MCP SQL Server repository as a `manager/` subfolder. It allows users to add, edit, delete, and test SQL Server MCP connections, which are persisted directly into Claude's `claude_desktop_config.json` file.

**Entry point:** `python -m manager.server` → starts FastAPI on `http://localhost:8090` and auto-opens the browser.

---

## Goals

- CRUD operations on `mcp_sqlserver` entries in `claude_desktop_config.json`
- Test a SQL Server connection (via pyodbc) before or after saving
- Show live connection status (online / offline) for each configured server
- Preserve all other entries in `claude_desktop_config.json` untouched

---

## Architecture

```
manager/
├── __init__.py
├── server.py             # FastAPI app: routes, startup, auto-browser open
├── config_manager.py     # Read/write claude_desktop_config.json
├── connection_tester.py  # Test a connection string via pyodbc
└── static/
    └── index.html        # Single-page app (vanilla HTML + CSS + JS)
```

New dependencies added to `pyproject.toml` as an optional dependency group:

```toml
[project.optional-dependencies]
manager = [
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
]
```

`pyodbc` is already a core dependency — no new package needed for connection testing.

---

## Config File Detection

`config_manager.py` auto-detects the Claude Desktop config path by platform:

| Platform | Path |
|----------|------|
| Windows  | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS    | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux    | `~/.config/Claude/claude_desktop_config.json` |

The manager only reads and writes keys under `mcpServers` where the `args` array contains the string `"mcp_sqlserver.server"` as a standalone element (i.e., `"mcp_sqlserver.server" in entry["args"]`). The Claude Desktop config format stores args as a JSON array — `["-m", "mcp_sqlserver.server", "--connection-string", "..."]` — so the filter must be an array-element membership check, not a substring search. All other `mcpServers` entries and top-level keys are preserved exactly as-is during every write.

Writes are performed atomically: the updated content is first written to a `.tmp` file alongside the target, then swapped in with `os.replace()`. This prevents config corruption if the process is interrupted mid-write.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/servers` | Returns list of all mcp_sqlserver entries with parsed parameters |
| `POST` | `/api/servers` | Adds a new entry; returns error if name already exists |
| `PUT` | `/api/servers/{name}` | Updates an existing entry by name |
| `DELETE` | `/api/servers/{name}` | Removes an entry by name |
| `POST` | `/api/test` | Tests a connection string via pyodbc; returns `{ok, error}`. Request body: `{"connection_string": "..."}` |

All endpoints return JSON. Errors return `{detail: "..."}` with appropriate HTTP status codes (400, 404, 409, 500).

---

## Data Model

Each MCP server entry is represented internally as:

```json
{
  "name": "db-vendite",
  "connection_string": "Driver={ODBC Driver 17 for SQL Server};Server=srv1;Database=Vendite;Trusted_Connection=yes",
  "max_rows": 100,
  "query_timeout": 30,
  "pool_size": 5,
  "pool_timeout": 30,
  "allowed_schemas": "dbo",
  "blacklist_tables": "sys_*,*_audit",
  "log_level": "INFO"
}
```

`config_manager.py` is responsible for translating between this model and the Claude Desktop config format (`command`, `args` array).

---

## UI (index.html)

Single HTML file with vanilla CSS and JS — no build step, no framework.

**Layout:**
- **Header:** title "SQL MCP Manager" + "Nuova Connessione" button
- **Server list:** one card per configured server
  - Each card shows: status dot (online/offline/unknown), name, server›database, schema tags, max-rows, timeout
  - Card actions: Test (⚡), Edit (✏️), Delete (🗑)
- **Inline form panel:** appears below the list when adding or editing
  - Fields: Name, Connection String (full width), Max Rows, Allowed Schemas, Blacklist Tables, Query Timeout, Pool Size, Pool Timeout
  - Actions: Cancel · Test Connection · Save

**Status indicator behavior:**
- On page load, the UI calls `POST /api/test` for each configured server in parallel
- Dot is grey (unknown) while testing, green (online) on success, red (offline) on failure
- "Test" button on each card re-runs the test for that server only

---

## Error Handling

- If `claude_desktop_config.json` does not exist, the manager shows an empty server list and creates the file on first save
- If the file is malformed JSON, the UI shows an error banner; no write is attempted
- Connection test errors surface the pyodbc error message in the UI (never crash the server)
- Duplicate server name on POST returns HTTP 409

---

## Installation & Usage

```bash
# Install manager dependencies
pip install -e ".[manager]"

# Start the manager
python -m manager.server
# Opens http://localhost:8090 automatically
```

---

## Out of Scope

- Managing non-mcp_sqlserver MCP entries (other tools, other databases)
- Authentication / access control (runs locally only)
- PostgreSQL / MySQL support (future roadmap)
- Export/import of config
