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
    """Convert data-model dict -> Claude Desktop config format (command + args)."""
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
    """Convert Claude Desktop args array -> data-model dict."""
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
