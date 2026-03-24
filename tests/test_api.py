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
    mock_add.assert_called_once_with(SAMPLE_ENTRY)


def test_post_server_duplicate_returns_409():
    with patch("manager.server.config_manager.add_server", side_effect=ValueError("already exists")):
        response = client.post("/api/servers", json=SAMPLE_ENTRY)
    assert response.status_code == 409


def test_post_server_invalid_input_returns_400():
    with patch("manager.server.config_manager.add_server", side_effect=ValueError("connection_string is required")):
        response = client.post("/api/servers", json=SAMPLE_ENTRY)
    assert response.status_code == 400


def test_put_server_success():
    with patch("manager.server.config_manager.update_server") as mock_update:
        response = client.put("/api/servers/db-test", json=SAMPLE_ENTRY)
    assert response.status_code == 200
    mock_update.assert_called_once_with("db-test", SAMPLE_ENTRY)


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


def test_put_server_name_mismatch_returns_400():
    response = client.put("/api/servers/different-name", json=SAMPLE_ENTRY)
    assert response.status_code == 400


def test_put_server_blank_connection_string_returns_400():
    entry = {**SAMPLE_ENTRY, "name": "db-test", "connection_string": "   "}
    with patch("manager.server.config_manager.update_server", side_effect=ValueError("connection_string is required")):
        response = client.put("/api/servers/db-test", json=entry)
    assert response.status_code == 400
