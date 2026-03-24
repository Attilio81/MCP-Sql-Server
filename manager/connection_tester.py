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
