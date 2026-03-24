from unittest.mock import patch, MagicMock
import manager.connection_tester as ct


def test_successful_connection():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (1,)
    with patch("manager.connection_tester.pyodbc.connect", return_value=mock_conn):
        result = ct.test_connection("Driver=...;Server=localhost")
    assert result["ok"] is True
    assert result["error"] is None


def test_failed_connection():
    with patch("manager.connection_tester.pyodbc.connect", side_effect=Exception("Connection refused")):
        result = ct.test_connection("Driver=...;Server=bad-host")
    assert result["ok"] is False
    assert "Connection refused" in result["error"]
