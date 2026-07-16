import json
import os
import pytest
from pathlib import Path
from manager.config_manager import (
    detect_config_path,
    read_config,
    read_databases,
    list_servers,
    add_server,
    update_server,
    delete_server,
    migrate_legacy_entries,
    get_dictionary_path,
    MCP_ENTRY_NAME,
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


@pytest.fixture
def paths(tmp_path):
    """(databases.json path, claude_desktop_config.json path) in a sandbox."""
    return tmp_path / "databases.json", tmp_path / "claude_desktop_config.json"


def test_detect_config_path_returns_path():
    path = detect_config_path()
    assert isinstance(path, Path)
    assert path.name == "claude_desktop_config.json"


def test_read_config_returns_empty_when_missing(tmp_path):
    result = read_config(tmp_path / "nonexistent.json")
    assert result == {"mcpServers": {}}


def test_read_config_malformed_json_raises_value_error(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError, match="malformed JSON"):
        read_config(cfg)


def test_add_server_writes_databases_json(paths):
    db_path, desktop = paths
    add_server(SAMPLE_ENTRY, db_path, desktop)
    data = read_databases(db_path)
    assert "db-test" in data
    assert data["db-test"]["connection_string"] == SAMPLE_ENTRY["connection_string"]
    assert "name" not in data["db-test"]


def test_add_server_syncs_single_desktop_entry(paths):
    db_path, desktop = paths
    add_server(SAMPLE_ENTRY, db_path, desktop)
    add_server({**SAMPLE_ENTRY, "name": "db-two"}, db_path, desktop)
    config = json.loads(desktop.read_text())
    sql_entries = [n for n, e in config["mcpServers"].items()
                   if "mcp_sqlserver.server" in e.get("args", [])]
    assert sql_entries == [MCP_ENTRY_NAME]
    assert "--databases" in config["mcpServers"][MCP_ENTRY_NAME]["args"]


def test_add_server_raises_on_duplicate(paths):
    db_path, desktop = paths
    add_server(SAMPLE_ENTRY, db_path, desktop)
    with pytest.raises(ValueError, match="already exists"):
        add_server(SAMPLE_ENTRY, db_path, desktop)


def test_add_server_raises_on_missing_connection_string(paths):
    db_path, desktop = paths
    with pytest.raises(ValueError, match="connection_string"):
        add_server({"name": "db-test", "connection_string": ""}, db_path, desktop)


def test_desktop_sync_preserves_other_entries(paths):
    db_path, desktop = paths
    desktop.write_text(json.dumps({
        "mcpServers": {"other-tool": {"command": "node", "args": ["server.js"]}}
    }), encoding="utf-8")
    add_server(SAMPLE_ENTRY, db_path, desktop)
    config = json.loads(desktop.read_text())
    assert "other-tool" in config["mcpServers"]
    assert MCP_ENTRY_NAME in config["mcpServers"]


def test_update_server_modifies_entry(paths):
    db_path, desktop = paths
    add_server(SAMPLE_ENTRY, db_path, desktop)
    update_server("db-test", {**SAMPLE_ENTRY, "max_rows": 200}, db_path, desktop)
    servers = list_servers(db_path, desktop)
    assert servers[0]["max_rows"] == 200


def test_update_server_raises_on_missing(paths):
    db_path, desktop = paths
    with pytest.raises(KeyError):
        update_server("nonexistent", SAMPLE_ENTRY, db_path, desktop)


def test_delete_server_removes_entry(paths):
    db_path, desktop = paths
    add_server(SAMPLE_ENTRY, db_path, desktop)
    delete_server("db-test", db_path, desktop)
    assert list_servers(db_path, desktop) == []
    # Desktop entry removed when no databases remain
    config = json.loads(desktop.read_text())
    assert MCP_ENTRY_NAME not in config["mcpServers"]


def test_delete_server_raises_on_missing(paths):
    db_path, desktop = paths
    with pytest.raises(KeyError):
        delete_server("nonexistent", db_path, desktop)


def test_write_is_atomic(paths, monkeypatch):
    """Original databases.json untouched and .tmp cleaned up if os.replace raises."""
    db_path, desktop = paths
    add_server(SAMPLE_ENTRY, db_path, desktop)
    original = db_path.read_text()

    def failing_replace(src, dst):
        raise OSError("simulated disk full")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(OSError):
        add_server({**SAMPLE_ENTRY, "name": "db-test2"}, db_path, desktop)

    assert db_path.read_text() == original
    assert not db_path.with_suffix(".tmp").exists()


# ── legacy migration ────────────────────────────────────────────────────────

LEGACY_CONFIG = {
    "mcpServers": {
        "db-old": {
            "command": "python",
            "args": ["-m", "mcp_sqlserver.server",
                     "--connection-string", "Driver=x;Database=Old",
                     "--max-rows", "50", "--allowed-schemas", "dbo"],
        },
        "other-tool": {"command": "node", "args": ["server.js"]},
    }
}


def test_migrate_legacy_entries(paths):
    db_path, desktop = paths
    desktop.write_text(json.dumps(LEGACY_CONFIG), encoding="utf-8")
    migrated = migrate_legacy_entries(db_path, desktop)
    assert migrated == 1
    data = read_databases(db_path)
    assert data["db-old"]["connection_string"] == "Driver=x;Database=Old"
    assert data["db-old"]["max_rows"] == 50
    config = json.loads(desktop.read_text())
    assert "db-old" not in config["mcpServers"]
    assert "other-tool" in config["mcpServers"]
    assert MCP_ENTRY_NAME in config["mcpServers"]


def test_list_servers_auto_migrates(paths):
    db_path, desktop = paths
    desktop.write_text(json.dumps(LEGACY_CONFIG), encoding="utf-8")
    servers = list_servers(db_path, desktop)
    assert [s["name"] for s in servers] == ["db-old"]


def test_migrate_is_idempotent(paths):
    db_path, desktop = paths
    desktop.write_text(json.dumps(LEGACY_CONFIG), encoding="utf-8")
    assert migrate_legacy_entries(db_path, desktop) == 1
    assert migrate_legacy_entries(db_path, desktop) == 0


# ── dictionary_file ────────────────────────────────────────────────────────

def test_get_dictionary_path_default(paths):
    db_path, desktop = paths
    add_server({"name": "db-test", "connection_string": "cs"}, db_path, desktop)
    path = get_dictionary_path("db-test", db_path)
    assert path == db_path.parent / "db-test_dictionary.md"


def test_get_dictionary_path_absolute(paths, tmp_path):
    db_path, desktop = paths
    abs_path = str(tmp_path / "my_dict.md")
    add_server({"name": "db-test", "connection_string": "cs", "dictionary_file": abs_path},
               db_path, desktop)
    assert get_dictionary_path("db-test", db_path) == Path(abs_path)


def test_get_dictionary_path_unknown_server(paths):
    db_path, _ = paths
    with pytest.raises(KeyError):
        get_dictionary_path("nonexistent", db_path)
