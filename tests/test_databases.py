# -*- coding: utf-8 -*-
"""Unit tests for the multi-database registry — no database required."""
import json

import pytest

from mcp_sqlserver import config, databases
from mcp_sqlserver.databases import DATABASES, get_database, is_multi, load_databases
from mcp_sqlserver.security import SecurityValidator


@pytest.fixture(autouse=True)
def _clean_registry():
    orig_databases_file = config.DATABASES_FILE
    orig_connection_string = config.CONNECTION_STRING
    DATABASES.clear()
    yield
    DATABASES.clear()
    config.DATABASES_FILE = orig_databases_file
    config.CONNECTION_STRING = orig_connection_string


def _write_config(tmp_path, data):
    path = tmp_path / "databases.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    config.DATABASES_FILE = str(path)
    config.CONNECTION_STRING = None
    return path


def test_load_multi(tmp_path):
    _write_config(tmp_path, {
        "sales": {"connection_string": "Driver=x;Database=Sales", "max_rows": 50,
                  "allowed_schemas": ["dbo"], "blacklist_tables": "sys_*,*_temp"},
        "wh": {"connection_string": "Driver=x;Database=WH"},
    })
    load_databases()
    assert set(DATABASES) == {"sales", "wh"}
    assert is_multi()
    sales = get_database("sales")
    assert sales.max_rows == 50
    assert sales.allowed_schemas == ["dbo"]
    assert sales.blacklist_tables == ["sys_*", "*_temp"]  # comma string accepted
    assert DATABASES["wh"].max_rows == 100  # default


def test_default_dictionary_next_to_config(tmp_path):
    path = _write_config(tmp_path, {"sales": {"connection_string": "Driver=x"}})
    load_databases()
    assert get_database("sales").dictionary_file == str(path.parent / "sales_dictionary.md")


def test_get_database_unknown_name(tmp_path):
    _write_config(tmp_path, {"sales": {"connection_string": "Driver=x"}})
    load_databases()
    with pytest.raises(KeyError, match="sales"):
        get_database("nope")


def test_get_database_required_when_multi(tmp_path):
    _write_config(tmp_path, {"a": {"connection_string": "x"}, "b": {"connection_string": "x"}})
    load_databases()
    with pytest.raises(KeyError, match="obbligatorio"):
        get_database()


def test_single_db_resolves_without_name(tmp_path):
    _write_config(tmp_path, {"only": {"connection_string": "x"}})
    load_databases()
    assert get_database().name == "only"
    assert not is_multi()


def test_legacy_mode_registers_default():
    config.DATABASES_FILE = None
    config.CONNECTION_STRING = "Driver=x;Database=Legacy"
    load_databases()
    assert set(DATABASES) == {"default"}
    assert get_database().connection_string == "Driver=x;Database=Legacy"


def test_missing_connection_string_raises(tmp_path):
    _write_config(tmp_path, {"bad": {"max_rows": 10}})
    with pytest.raises(ValueError, match="connection_string"):
        load_databases()


def test_per_database_security_isolation():
    """is_table_allowed must honour per-db lists, not the global config."""
    allowed, _ = SecurityValidator.is_table_allowed(
        "admin.Secrets", allowed_schemas=["dbo"], blacklist=[])
    assert not allowed
    allowed, _ = SecurityValidator.is_table_allowed(
        "admin.Secrets", allowed_schemas=["admin"], blacklist=[])
    assert allowed
    allowed, _ = SecurityValidator.is_table_allowed(
        "sys_logs", allowed_schemas=[], blacklist=["sys_*"])
    assert not allowed
