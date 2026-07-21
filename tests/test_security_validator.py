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
from mcp_sqlserver import config  # noqa: E402
from mcp_sqlserver.security import SecurityValidator  # noqa: E402
from mcp_sqlserver.helpers import format_table_data, format_csv, format_json  # noqa: E402
from mcp_sqlserver.tools.execute_query import ensure_top  # noqa: E402


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
        import mcp_sqlserver.config as mod
        self._orig_blacklist = mod.BLACKLIST_TABLES
        self._orig_schemas = mod.ALLOWED_SCHEMAS
        mod.BLACKLIST_TABLES = ["sys_*", "*_temp"]
        mod.ALLOWED_SCHEMAS = []

    def tearDown(self):
        import mcp_sqlserver.config as mod
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
        import mcp_sqlserver.config as mod
        self._orig_schemas = mod.ALLOWED_SCHEMAS
        self._orig_blacklist = mod.BLACKLIST_TABLES
        mod.ALLOWED_SCHEMAS = ["dbo", "sales"]
        mod.BLACKLIST_TABLES = []

    def tearDown(self):
        import mcp_sqlserver.config as mod
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
        ok, _ = SecurityValidator.validate_query("SELECT " + "a" * (config.MAX_QUERY_LENGTH + 1))
        self.assertFalse(ok)

    def test_valid_where_clause(self):
        ok, msg = SecurityValidator.validate_query("SELECT Name FROM Users WHERE Id = 1")
        self.assertTrue(ok, msg)


class TestExtractTableNames(unittest.TestCase):
    """Tests for SecurityValidator.extract_table_names"""

    def test_simple_from(self):
        self.assertEqual(SecurityValidator.extract_table_names("SELECT * FROM Users"), ["USERS"])

    def test_schema_qualified(self):
        self.assertEqual(SecurityValidator.extract_table_names("SELECT * FROM dbo.Users"), ["DBO.USERS"])

    def test_bracket_quoted(self):
        self.assertEqual(SecurityValidator.extract_table_names("SELECT * FROM [dbo].[Users]"), ["DBO.USERS"])

    def test_join(self):
        tables = SecurityValidator.extract_table_names(
            "SELECT * FROM Orders o INNER JOIN Customers c ON o.CustId = c.Id"
        )
        self.assertEqual(tables, ["ORDERS", "CUSTOMERS"])

    def test_comma_join(self):
        tables = SecurityValidator.extract_table_names("SELECT * FROM Orders o, Customers c WHERE o.CustId = c.Id")
        self.assertEqual(tables, ["ORDERS", "CUSTOMERS"])

    def test_subquery(self):
        tables = SecurityValidator.extract_table_names(
            "SELECT * FROM (SELECT Id FROM Secrets) s JOIN Users u ON u.Id = s.Id"
        )
        self.assertIn("SECRETS", tables)
        self.assertIn("USERS", tables)

    def test_comma_join_after_derived_table(self):
        tables = SecurityValidator.extract_table_names("SELECT * FROM (SELECT 1 AS c) x, Secrets")
        self.assertIn("SECRETS", tables)

    def test_cross_apply(self):
        tables = SecurityValidator.extract_table_names("SELECT * FROM Users u CROSS APPLY Secrets s")
        self.assertEqual(tables, ["USERS", "SECRETS"])

    def test_in_subquery(self):
        tables = SecurityValidator.extract_table_names(
            "SELECT * FROM Users WHERE Id IN (SELECT UserId FROM Secrets)"
        )
        self.assertIn("SECRETS", tables)

    def test_string_literal_ignored(self):
        tables = SecurityValidator.extract_table_names("SELECT * FROM Users WHERE Name = 'from secrets'")
        self.assertEqual(tables, ["USERS"])

    def test_select_list_commas_not_tables(self):
        tables = SecurityValidator.extract_table_names("SELECT a, b, c FROM Users")
        self.assertEqual(tables, ["USERS"])


class TestExecuteQueryBlacklist(unittest.TestCase):
    """execute_query must enforce blacklist on tables referenced in free-form SELECTs."""

    def setUp(self):
        import mcp_sqlserver.config as mod
        self._orig_blacklist = mod.BLACKLIST_TABLES
        mod.BLACKLIST_TABLES = ["secrets"]

    def tearDown(self):
        import mcp_sqlserver.config as mod
        mod.BLACKLIST_TABLES = self._orig_blacklist

    def _blocked(self, query):
        for table in SecurityValidator.extract_table_names(query):
            allowed, _ = SecurityValidator.is_table_allowed(table)
            if not allowed:
                return True
        return False

    def test_direct_select_blocked(self):
        self.assertTrue(self._blocked("SELECT * FROM Secrets"))

    def test_join_blocked(self):
        self.assertTrue(self._blocked("SELECT * FROM Users u JOIN Secrets s ON u.Id = s.UserId"))

    def test_comma_join_blocked(self):
        self.assertTrue(self._blocked("SELECT * FROM Users, Secrets"))

    def test_subquery_blocked(self):
        self.assertTrue(self._blocked("SELECT * FROM Users WHERE Id IN (SELECT UserId FROM Secrets)"))

    def test_allowed_table_passes(self):
        self.assertFalse(self._blocked("SELECT * FROM Users"))


class TestEnsureTop(unittest.TestCase):
    """Tests for ensure_top row-limit injection."""

    def test_adds_top(self):
        self.assertEqual(ensure_top("SELECT * FROM Users", 100), "SELECT TOP 100 * FROM Users")

    def test_respects_distinct(self):
        self.assertEqual(ensure_top("SELECT DISTINCT Name FROM Users", 100),
                         "SELECT DISTINCT TOP 100 Name FROM Users")

    def test_existing_top_untouched(self):
        q = "SELECT TOP 5 * FROM Users"
        self.assertEqual(ensure_top(q, 100), q)

    def test_existing_top_paren_untouched(self):
        q = "SELECT TOP(5) * FROM Users"
        self.assertEqual(ensure_top(q, 100), q)

    def test_topic_column_does_not_skip_limit(self):
        """Regression: substring match on 'TOP' skipped the limit for columns like Topic."""
        result = ensure_top("SELECT Topic FROM Posts", 100)
        self.assertEqual(result, "SELECT TOP 100 Topic FROM Posts")


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


class TestFormatCsvJson(unittest.TestCase):
    """Tests for format_csv / format_json output formats."""

    def test_csv_basic(self):
        result = format_csv(["Name", "Age"], [("Alice", 30)])
        self.assertIn("Name,Age", result)
        self.assertIn("Alice,30", result)

    def test_csv_quotes_comma_values(self):
        result = format_csv(["Val"], [("a,b",)])
        self.assertIn('"a,b"', result)

    def test_csv_null_as_empty(self):
        result = format_csv(["A", "B"], [(None, 1)])
        self.assertIn(",1", result)

    def test_csv_no_truncation(self):
        long_val = "x" * 200
        result = format_csv(["Col"], [(long_val,)])
        self.assertIn(long_val, result)

    def test_csv_empty(self):
        self.assertEqual(format_csv(["A"], []), "*Nessun dato trovato*")

    def test_json_basic(self):
        result = format_json(["Name", "Age"], [("Alice", 30)])
        self.assertIn('"Name": "Alice"', result)
        self.assertIn('"Age": 30', result)

    def test_json_null(self):
        result = format_json(["A"], [(None,)])
        self.assertIn('"A": null', result)

    def test_json_non_serializable_via_str(self):
        from decimal import Decimal
        result = format_json(["Amount"], [(Decimal("1.50"),)])
        self.assertIn('"1.50"', result)

    def test_json_empty(self):
        self.assertEqual(format_json(["A"], []), "*Nessun dato trovato*")


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
