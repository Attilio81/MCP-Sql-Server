# -*- coding: utf-8 -*-
"""
Security validation for MCP SQL Server.
Multi-layer validator for table names and SQL queries.
"""

import re
import fnmatch
import logging
from typing import Optional

from mcp_sqlserver import config

logger = logging.getLogger(__name__)

# DML / DDL / admin keywords that must never appear in user queries
DANGEROUS_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE",
    "EXEC", "EXECUTE", "GRANT", "REVOKE", "BACKUP", "RESTORE",
    "MERGE", "CALL", "SIGNAL", "RESIGNAL", "RENAME",
    # Data exfiltration / out-of-band
    "INTO OUTFILE", "INTO DUMPFILE", "LOAD_FILE",
    "OPENROWSET", "OPENDATASOURCE", "OPENQUERY", "OPENXML",
    "BULK INSERT", "BULK",
    # Timing / DoS attacks
    "WAITFOR", "SLEEP", "BENCHMARK",
    # Privilege escalation
    "DBCC", "RECONFIGURE", "SHUTDOWN",
    # Stored procedure / shell execution
    "XP_", "SP_OACREATE", "SP_OAMETHOD", "SP_ADDLOGIN",
]

# Regex patterns that indicate injection attempts regardless of keyword position
INJECTION_PATTERNS: list[tuple[str, str]] = [
    # Stacked / batched statements
    (r';', "Stacked statements (semicolons) are not allowed"),
    # Full-width / Unicode lookalike semicolon (U+FF1B)
    (r'；', "Unicode lookalike semicolons are not allowed"),
    # Any SQL comment style
    (r'--', "SQL comments are not allowed"),
    (r'/\*', "SQL block comments are not allowed"),
    # Encoding / obfuscation tricks
    (r'\bCHAR\s*\(', "CHAR() encoding is not allowed"),
    (r'\bNCHAR\s*\(', "NCHAR() encoding is not allowed"),
    (r'\b0x[0-9A-Fa-f]+', "Hexadecimal literals are not allowed"),
    # Dangerous string concatenation / dynamic SQL
    (r'\bEXEC\s*\(', "Dynamic EXEC() is not allowed"),
    (r'\bEXECUTE\s*\(', "Dynamic EXECUTE() is not allowed"),
    (r'\bsp_executesql\b', "sp_executesql is not allowed"),
    (r'\bxp_cmdshell\b', "xp_cmdshell is not allowed"),
    # NULL byte injection
    (r'\x00', "Null bytes are not allowed"),
    # UNION-based exfiltration (still block even inside SELECT)
    (r'\bUNION\b', "UNION queries are not allowed"),
    # Subquery exfiltration via INTO / file ops
    (r'\bINTO\s+OUTFILE\b', "INTO OUTFILE is not allowed"),
    (r'\bINTO\s+DUMPFILE\b', "INTO DUMPFILE is not allowed"),
    # Privilege / config changes
    (r'\bDBCC\b', "DBCC commands are not allowed"),
    (r'\bSHUTDOWN\b', "SHUTDOWN is not allowed"),
    # Timing attacks
    (r'\bWAITFOR\b', "WAITFOR is not allowed"),
]


class SecurityValidator:
    """Multi-layer validator for table names and SQL queries."""

    # Allowed characters for identifiers (schema / table names).
    # Brackets are stripped before validation to handle [dbo].[MyTable] syntax.
    _IDENTIFIER_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalize(text: str) -> str:
        """
        Normalise a query string before security checks:
        - Remove null bytes
        - Collapse whitespace / newlines to single spaces
        - Replace full-width lookalike characters (e.g. ；ꓸ) with ASCII equivalents
        - Fold to upper-case
        The original query is executed as-is; this copy is used only for validation.
        """
        # Strip null bytes
        text = text.replace('\x00', '')
        # Full-width semicolon → ASCII semicolon
        text = text.replace('\uff1b', ';')
        # Collapse all whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.upper().strip()

    @staticmethod
    def _strip_brackets(name: str) -> str:
        """Remove optional T-SQL bracket quoting: [dbo] → dbo"""
        return name.strip().lstrip('[').rstrip(']')

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    @classmethod
    def is_table_allowed(cls, table_name: str, schema: Optional[str] = None) -> tuple[bool, str]:
        """
        Check if a table is allowed based on blacklist and schema rules.
        Returns (is_allowed, error_message).
        """
        # Strip bracket quoting before processing
        raw = table_name.strip()
        parts = [cls._strip_brackets(p) for p in raw.split(".")]

        if len(parts) == 2:
            schema, table = parts
        elif len(parts) == 1:
            table = parts[0]
            schema = schema or "dbo"
        else:
            return False, f"Invalid table name: {table_name}"

        # Validate identifier format to prevent injection via table/schema names
        if not cls._IDENTIFIER_RE.match(table):
            return False, f"Table name contains invalid characters: {table}"
        if not cls._IDENTIFIER_RE.match(schema):
            return False, f"Schema name contains invalid characters: {schema}"

        # Check allowed schemas whitelist
        if config.ALLOWED_SCHEMAS and schema.lower() not in config.ALLOWED_SCHEMAS:
            return False, (
                f"Schema '{schema}' is not authorised. "
                f"Allowed schemas: {', '.join(config.ALLOWED_SCHEMAS)}"
            )

        # Check blacklist with wildcard support
        for pattern in config.BLACKLIST_TABLES:
            if fnmatch.fnmatch(table.lower(), pattern.lower()):
                return False, f"Table '{table}' matches blacklist pattern '{pattern}'"
            if fnmatch.fnmatch(f"{schema}.{table}".lower(), pattern.lower()):
                return False, f"Table '{schema}.{table}' matches blacklist pattern '{pattern}'"

        return True, ""

    @classmethod
    def validate_query(cls, query: str) -> tuple[bool, str]:
        """
        Validate a query is safe to execute.
        Returns (is_valid, error_message).

        Defence layers (in order):
          1. Length cap — prevents DoS via huge payloads
          2. Null-byte rejection (before normalisation)
          3. Unicode / whitespace normalisation
          4. Must start with SELECT (no other statement type allowed)
          5. Stacked-statement / comment patterns (regex, on normalised text)
          6. Dangerous keyword word-boundary check (on normalised text)
        """
        # 1. Length guard
        if len(query) > config.MAX_QUERY_LENGTH:
            return False, (
                f"Query exceeds maximum allowed length "
                f"({len(query)} > {config.MAX_QUERY_LENGTH} characters)"
            )

        # 2. Reject null bytes before normalisation strips them
        if '\x00' in query:
            return False, "Blocked: Null bytes are not allowed"

        # 3. Normalise for validation (original is used for execution)
        normalised = cls._normalize(query)

        # 4. Must be a SELECT statement
        if not normalised.startswith("SELECT"):
            return False, "Only SELECT statements are allowed"

        # 5. Injection pattern checks (on normalised text)
        for pattern, description in INJECTION_PATTERNS:
            if re.search(pattern, normalised, re.IGNORECASE):
                logger.warning("Blocked query — pattern '%s' matched: %.120s", pattern, query)
                return False, f"Blocked: {description}"

        # 6. Dangerous keyword word-boundary check
        for keyword in DANGEROUS_KEYWORDS:
            # keywords with spaces (e.g. "INTO OUTFILE") are already caught above;
            # single-token keywords get a word-boundary check to avoid false positives
            if ' ' in keyword:
                continue
            if re.search(r'\b' + re.escape(keyword) + r'\b', normalised):
                logger.warning("Blocked query — keyword '%s' found: %.120s", keyword, query)
                return False, f"Keyword '{keyword}' is not allowed"

        return True, ""
