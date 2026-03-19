# -*- coding: utf-8 -*-
"""
Unit tests for SecurityValidator and format_table_data.
These tests do NOT require a database connection.
"""

import sys
import os
import unittest

# Ensure the src directory is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Import after path setup — the module no longer calls _parse_args() at import time
from mcp_sqlserver.server import SecurityValidator, format_table_data  # noqa: E402


class TestSecurityValidatorTableAllowed(unittest.TestCase):
    """Tests for SecurityValidator.is_table_allowed"""

    def test_simple_table_allowed(self):
        allowed, msg = SecurityValidator.is_table_allowed("Users")
        self.assertTrue(allowed, msg)

    def test_schema_qualified_table(self):
        allowed, msg = SecurityValidator.is_table_allowed("dbo.Users")
        self.assertTrue(allowed, msg)

    def test_bracket_quoted_table(self):
        allowed, msg = SecurityValidator.is_table_allowed("[dbo].[Users]")
        self.assertTrue(allowed, msg)

    def test_invalid_characters_in_table(self):
        allowed, _ = SecurityValidator.is_table_allowed("dbo.Users; DROP TABLE")
        self.assertFalse(allowed)

    def test_invalid_characters_in_schema(self):
        allowed, _ = SecurityValidator.is_table_allowed("db--o.Users")
        self.assertFalse(allowed)

    def test_too_many_parts(self):
        allowed, _ = SecurityValidator.is_table_allowed("server.dbo.Users")
        self.assertFalse(allowed)

    def test_default_schema_is_dbo(self):
        """When no schema is specified, default should be dbo."""
        allowed, msg = SecurityValidator.is_table_allowed("Orders")
        self.assertTrue(allowed, msg)


class TestSecurityValidatorBlacklist(unittest.TestCase):
    """Tests for blacklist / allowed_schemas interaction."""

    def setUp(self):
        """Save and set module-level config for blacklist tests."""
        import mcp_sqlserver.server as mod
        self._orig_blacklist = mod.BLACKLIST_TABLES
        self._orig_schemas = mod.ALLOWED_SCHEMAS
        mod.BLACKLIST_TABLES = ["sys_*", "*_temp"]
        mod.ALLOWED_SCHEMAS = []

    def tearDown(self):
        import mcp_sqlserver.server as mod
        mod.BLACKLIST_TABLES = self._orig_blacklist
        mod.ALLOWED_SCHEMAS = self._orig_schemas

    def test_blacklist_wildcard_prefix(self):
        allowed, _ = SecurityValidator.is_table_allowed("sys_logs")
        self.assertFalse(allowed)

    def test_blacklist_wildcard_suffix(self):
        allowed, _ = SecurityValidator.is_table_allowed("cache_temp")
        self.assertFalse(allowed)

    def test_not_blacklisted(self):
        allowed, msg = SecurityValidator.is_table_allowed("Customers")
        self.assertTrue(allowed, msg)


class TestSecurityValidatorAllowedSchemas(unittest.TestCase):

    def setUp(self):
        import mcp_sqlserver.server as mod
        self._orig_schemas = mod.ALLOWED_SCHEMAS
        self._orig_blacklist = mod.BLACKLIST_TABLES
        mod.ALLOWED_SCHEMAS = ["dbo", "sales"]
        mod.BLACKLIST_TABLES = []

    def tearDown(self):
        import mcp_sqlserver.server as mod
        mod.ALLOWED_SCHEMAS = self._orig_schemas
        mod.BLACKLIST_TABLES = self._orig_blacklist

    def test_allowed_schema(self):
        allowed, msg = SecurityValidator.is_table_allowed("dbo.Users")
        self.assertTrue(allowed, msg)

    def test_allowed_schema_case_insensitive(self):
        allowed, msg = SecurityValidator.is_table_allowed("DBO.Users")
        self.assertTrue(allowed, msg)

    def test_disallowed_schema(self):
        allowed, _ = SecurityValidator.is_table_allowed("admin.Secrets")
        self.assertFalse(allowed)


class TestSecurityValidatorQuery(unittest.TestCase):
    """Tests for SecurityValidator.validate_query"""

    def test_valid_select(self):
        ok, msg = SecurityValidator.validate_query("SELECT * FROM Users")
        self.assertTrue(ok, msg)

    def test_reject_insert(self):
        ok, _ = SecurityValidator.validate_query("INSERT INTO Users VALUES (1)")
        self.assertFalse(ok)

    def test_reject_drop(self):
        ok, _ = SecurityValidator.validate_query("DROP TABLE Users")
        self.assertFalse(ok)

    def test_reject_semicolon(self):
        ok, _ = SecurityValidator.validate_query("SELECT 1; DROP TABLE Users")
        self.assertFalse(ok)

    def test_reject_comment_dash(self):
        ok, _ = SecurityValidator.validate_query("SELECT 1 -- comment")
        self.assertFalse(ok)

    def test_reject_block_comment(self):
        ok, _ = SecurityValidator.validate_query("SELECT /* evil */ 1")
        self.assertFalse(ok)

    def test_reject_union(self):
        ok, _ = SecurityValidator.validate_query("SELECT 1 UNION SELECT 2")
        self.assertFalse(ok)

    def test_reject_waitfor(self):
        ok, _ = SecurityValidator.validate_query("SELECT 1 WAITFOR DELAY '00:00:05'")
        self.assertFalse(ok)

    def test_reject_xp_cmdshell(self):
        ok, _ = SecurityValidator.validate_query("SELECT 1 xp_cmdshell 'dir'")
        self.assertFalse(ok)

    def test_reject_exec_dynamic(self):
        ok, _ = SecurityValidator.validate_query("SELECT 1 EXEC('SELECT 2')")
        self.assertFalse(ok)

    def test_reject_null_byte(self):
        ok, _ = SecurityValidator.validate_query("SELECT \x001")
        self.assertFalse(ok)

    def test_reject_unicode_semicolon(self):
        ok, _ = SecurityValidator.validate_query("SELECT 1\uff1b DROP TABLE Users")
        self.assertFalse(ok)

    def test_reject_too_long_query(self):
        ok, _ = SecurityValidator.validate_query("SELECT " + "a" * 5000)
        self.assertFalse(ok)

    def test_valid_where_clause(self):
        ok, msg = SecurityValidator.validate_query("SELECT Name FROM Users WHERE Id = 1")
        self.assertTrue(ok, msg)


class TestFormatTableData(unittest.TestCase):

    def test_empty_rows(self):
        result = format_table_data(["col1"], [])
        self.assertEqual(result, "*Nessun dato trovato*")

    def test_basic_formatting(self):
        result = format_table_data(["Name", "Age"], [("Alice", 30)])
        self.assertIn("Alice", result)
        self.assertIn("30", result)
        self.assertIn("| Name | Age |", result)

    def test_null_value(self):
        result = format_table_data(["Name"], [(None,)])
        self.assertIn("NULL", result)

    def test_pipe_in_value_escaped(self):
        result = format_table_data(["Val"], [("a|b",)])
        self.assertIn("a\\|b", result)
        # Should not produce a raw unescaped pipe that breaks the table
        lines = result.strip().split("\n")
        data_line = lines[-1]
        # The data row should have exactly 2 unescaped pipes (start and end)
        unescaped_pipes = len(data_line.split("\\|"))
        self.assertGreaterEqual(unescaped_pipes, 1)

    def test_truncation(self):
        long_val = "x" * 100
        result = format_table_data(["Col"], [(long_val,)], max_col_width=20)
        self.assertIn("...", result)
        # Truncated value should not exceed max_col_width
        lines = result.strip().split("\n")
        data_line = lines[-1]
        # Extract value between pipes
        parts = data_line.strip("|").strip().split("|")
        self.assertLessEqual(len(parts[0].strip()), 20)


class TestNormalize(unittest.TestCase):

    def test_collapses_whitespace(self):
        result = SecurityValidator._normalize("SELECT  \n  *  FROM   Users")
        self.assertEqual(result, "SELECT * FROM USERS")

    def test_removes_null_bytes(self):
        result = SecurityValidator._normalize("SEL\x00ECT")
        self.assertNotIn("\x00", result)

    def test_replaces_fullwidth_semicolon(self):
        result = SecurityValidator._normalize("SELECT 1\uff1b DROP")
        self.assertIn(";", result)


class TestStripBrackets(unittest.TestCase):

    def test_strip_brackets(self):
        self.assertEqual(SecurityValidator._strip_brackets("[dbo]"), "dbo")

    def test_no_brackets(self):
        self.assertEqual(SecurityValidator._strip_brackets("dbo"), "dbo")

    def test_strip_with_spaces(self):
        self.assertEqual(SecurityValidator._strip_brackets("  [Users]  "), "Users")


if __name__ == "__main__":
    unittest.main()
