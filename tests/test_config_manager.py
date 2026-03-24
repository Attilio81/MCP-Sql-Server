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
    get_dictionary_path,   # ← add this
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


def test_read_config_malformed_json_raises_value_error(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError, match="malformed JSON"):
        read_config(cfg)


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


def test_add_server_raises_on_missing_connection_string(tmp_path):
    cfg = tmp_path / "config.json"
    with pytest.raises(ValueError, match="connection_string"):
        add_server({"name": "db-test", "connection_string": ""}, path=cfg)


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
    """Verify original file is untouched and .tmp is cleaned up if os.replace raises."""
    cfg = tmp_path / "config.json"
    add_server(SAMPLE_ENTRY, path=cfg)
    original = cfg.read_text()

    def failing_replace(src, dst):
        raise OSError("simulated disk full")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(OSError):
        add_server({**SAMPLE_ENTRY, "name": "db-test2"}, path=cfg)

    assert cfg.read_text() == original
    # .tmp file should be cleaned up
    assert not cfg.with_suffix(".tmp").exists()


# ── dictionary_file ────────────────────────────────────────────────────────

def test_serialize_entry_includes_dictionary_file():
    entry = {
        "name": "db-test",
        "connection_string": "Driver=...;Server=s;Database=d;",
        "dictionary_file": "/tmp/my_dict.md",
    }
    result = _serialize_entry(entry)
    assert "--dictionary-file" in result["args"]
    idx = result["args"].index("--dictionary-file")
    assert result["args"][idx + 1] == "/tmp/my_dict.md"


def test_serialize_entry_omits_empty_dictionary_file():
    entry = {
        "name": "db-test",
        "connection_string": "Driver=...;Server=s;Database=d;",
        "dictionary_file": "",
    }
    result = _serialize_entry(entry)
    assert "--dictionary-file" not in result["args"]


def test_parse_entry_reads_dictionary_file():
    args = ["-m", "mcp_sqlserver.server", "--connection-string", "cs", "--dictionary-file", "/tmp/d.md"]
    result = _parse_entry("srv", args)
    assert result["dictionary_file"] == "/tmp/d.md"


def test_get_dictionary_path_default(tmp_path):
    """Returns default path when dictionary_file not set."""
    config_data = {
        "mcpServers": {
            "db-test": {
                "command": "python",
                "args": ["-m", "mcp_sqlserver.server", "--connection-string", "cs"],
            }
        }
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data))
    path = get_dictionary_path("db-test", config_file)
    assert path.name == "semantic_dictionary.md"


def test_get_dictionary_path_absolute(tmp_path):
    """Returns absolute path as-is."""
    abs_path = str(tmp_path / "my_dict.md")
    config_data = {
        "mcpServers": {
            "db-test": {
                "command": "python",
                "args": ["-m", "mcp_sqlserver.server", "--connection-string", "cs",
                         "--dictionary-file", abs_path],
            }
        }
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data))
    result = get_dictionary_path("db-test", config_file)
    assert result == Path(abs_path)


def test_get_dictionary_path_unknown_server(tmp_path):
    config_data = {"mcpServers": {}}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data))
    with pytest.raises(KeyError):
        get_dictionary_path("nonexistent", config_file)
