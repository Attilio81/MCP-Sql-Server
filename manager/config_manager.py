# -*- coding: utf-8 -*-
"""
Storage backend for the SQL MCP Manager.

Databases live in a single JSON file (databases.json). The Claude Desktop
config gets exactly one mcp_sqlserver entry pointing at that file via
--databases; it is kept in sync on every write. Legacy per-database
entries found in claude_desktop_config.json are migrated automatically
on first read.
"""
import json
import os
import sys
from pathlib import Path
from typing import Optional

MCP_ENTRY_NAME = "sqlserver"


def detect_config_path() -> Path:
    """Return platform-specific path to claude_desktop_config.json."""
    if sys.platform == "win32":
        return Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def databases_path() -> Path:
    """Return the path of databases.json (env override: MCP_SQLSERVER_DATABASES)."""
    env = os.getenv("MCP_SQLSERVER_DATABASES")
    if env:
        return Path(env)
    return Path.home() / ".mcp_sqlserver" / "databases.json"


def read_config(path: Path) -> dict:
    """Return parsed Claude Desktop config; {'mcpServers': {}} if file missing."""
    if not path.exists():
        return {"mcpServers": {}}
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"claude_desktop_config.json is malformed JSON: {exc}") from exc


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def read_databases(db_path: Optional[Path] = None) -> dict:
    """Return the databases.json content as {name: entry-dict}."""
    if db_path is None:
        db_path = databases_path()
    if not db_path.exists():
        return {}
    try:
        return json.loads(db_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"databases.json is malformed JSON: {exc}") from exc


def _write_databases(data: dict, db_path: Optional[Path] = None,
                     desktop_path: Optional[Path] = None) -> None:
    """Write databases.json and keep the Desktop config's single entry in sync."""
    if db_path is None:
        db_path = databases_path()
    _atomic_write(db_path, data)
    _sync_desktop_config(db_path, desktop_path)


def _sync_desktop_config(db_path: Path, desktop_path: Optional[Path] = None) -> None:
    """Ensure exactly one mcp_sqlserver entry (--databases) in the Desktop config."""
    if desktop_path is None:
        desktop_path = detect_config_path()
    config = read_config(desktop_path)
    servers = config.setdefault("mcpServers", {})
    # Drop every legacy per-database mcp_sqlserver entry
    for name in [n for n, e in servers.items() if "mcp_sqlserver.server" in e.get("args", [])]:
        del servers[name]
    if read_databases(db_path):
        servers[MCP_ENTRY_NAME] = {
            "command": "python",
            "args": ["-m", "mcp_sqlserver.server", "--databases", str(db_path)],
        }
    _atomic_write(desktop_path, config)


# ------------------------------------------------------------------ #
#  Legacy migration                                                    #
# ------------------------------------------------------------------ #

def _parse_legacy_args(name: str, args: list) -> dict:
    """Convert a legacy Claude Desktop args array -> data-model dict."""
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


def migrate_legacy_entries(db_path: Optional[Path] = None,
                           desktop_path: Optional[Path] = None) -> int:
    """Move old per-database mcp_sqlserver entries from the Desktop config
    into databases.json. Returns the number of migrated entries."""
    if desktop_path is None:
        desktop_path = detect_config_path()
    if db_path is None:
        db_path = databases_path()

    config = read_config(desktop_path)
    legacy = {}
    for name, entry in config.get("mcpServers", {}).items():
        args = entry.get("args", [])
        if "mcp_sqlserver.server" in args and "--databases" not in args:
            parsed = _parse_legacy_args(name, args)
            if parsed.get("connection_string"):
                parsed.pop("name", None)
                legacy[name] = parsed

    if not legacy:
        return 0

    databases = read_databases(db_path)
    for name, entry in legacy.items():
        databases.setdefault(name, entry)
    _write_databases(databases, db_path, desktop_path)
    return len(legacy)


# ------------------------------------------------------------------ #
#  CRUD (data-model dicts, same shape the API always used)             #
# ------------------------------------------------------------------ #

def list_servers(db_path: Optional[Path] = None,
                 desktop_path: Optional[Path] = None) -> list:
    """Return all databases as data-model dicts (with 'name'). Auto-migrates legacy entries."""
    migrate_legacy_entries(db_path, desktop_path)
    databases = read_databases(db_path)
    return [{"name": name, **entry} for name, entry in databases.items()]


def add_server(entry: dict, db_path: Optional[Path] = None,
               desktop_path: Optional[Path] = None) -> None:
    """Add a database. Raises ValueError if name exists or connection_string missing."""
    if not entry.get("connection_string", "").strip():
        raise ValueError("connection_string is required")
    databases = read_databases(db_path)
    name = entry["name"]
    if name in databases:
        raise ValueError(f"Server '{name}' already exists")
    databases[name] = {k: v for k, v in entry.items() if k != "name"}
    _write_databases(databases, db_path, desktop_path)


def update_server(name: str, entry: dict, db_path: Optional[Path] = None,
                  desktop_path: Optional[Path] = None) -> None:
    """Update a database. Raises KeyError if missing, ValueError if connection_string missing."""
    if not entry.get("connection_string", "").strip():
        raise ValueError("connection_string is required")
    databases = read_databases(db_path)
    if name not in databases:
        raise KeyError(f"Server '{name}' not found")
    databases[name] = {k: v for k, v in entry.items() if k != "name"}
    _write_databases(databases, db_path, desktop_path)


def delete_server(name: str, db_path: Optional[Path] = None,
                  desktop_path: Optional[Path] = None) -> None:
    """Delete a database. Raises KeyError if not found."""
    databases = read_databases(db_path)
    if name not in databases:
        raise KeyError(f"Server '{name}' not found")
    del databases[name]
    _write_databases(databases, db_path, desktop_path)


def get_dictionary_path(server_name: str, db_path: Optional[Path] = None) -> Path:
    """Resolved dictionary file path for a database.

    Default (matching the server side): <databases.json dir>/<name>_dictionary.md.
    Relative paths resolve against the databases.json directory.
    Raises KeyError if the database is not found.
    """
    if db_path is None:
        db_path = databases_path()
    databases = read_databases(db_path)
    if server_name not in databases:
        raise KeyError(f"Server '{server_name}' not found")
    raw = databases[server_name].get("dictionary_file") or f"{server_name}_dictionary.md"
    p = Path(raw)
    if not p.is_absolute():
        p = db_path.parent / p
    return p
