# -*- coding: utf-8 -*-
"""
Configuration management for MCP SQL Server.
Handles CLI argument parsing, environment variables, and module-level settings.
"""

import argparse
import os
import logging
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file (if present)
load_dotenv()


_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _parse_args():
    """Parse command line arguments. CLI args take precedence over .env / environment variables."""
    parser = argparse.ArgumentParser(description="MCP SQL Server")
    parser.add_argument(
        "--connection-string",
        help="SQL Server connection string (e.g. Driver={ODBC Driver 17 for SQL Server};Server=...)",
    )
    parser.add_argument("--max-rows", type=int, help="Maximum rows returned per query (default: 100)")
    parser.add_argument("--query-timeout", type=int, help="Query timeout in seconds (default: 30)")
    parser.add_argument("--pool-size", type=int, help="Connection pool size (default: 5)")
    parser.add_argument("--pool-timeout", type=int, help="Connection pool timeout in seconds (default: 30)")
    parser.add_argument(
        "--blacklist-tables",
        help="Comma-separated list of blacklisted tables, supports wildcards (e.g. sys_*,*_temp)",
    )
    parser.add_argument(
        "--allowed-schemas",
        help="Comma-separated list of allowed schemas (empty = all schemas allowed)",
    )
    parser.add_argument("--log-level", help="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)")
    parser.add_argument(
        "--dictionary-file",
        help="Path del file dizionario semantico (default: semantic_dictionary.md)",
    )
    return parser.parse_args()


def _load_config():
    """Load configuration from CLI args and environment variables. Called lazily."""
    global CONNECTION_STRING, MAX_ROWS, QUERY_TIMEOUT, POOL_SIZE, POOL_TIMEOUT
    global LOG_LEVEL, BLACKLIST_TABLES, ALLOWED_SCHEMAS, DICTIONARY_FILE, logger

    _args = _parse_args()

    # Configuration — CLI args take precedence over environment variables / .env
    CONNECTION_STRING = _args.connection_string or os.getenv("SQL_CONNECTION_STRING")
    MAX_ROWS = _args.max_rows if _args.max_rows is not None else int(os.getenv("MAX_ROWS", "100"))
    QUERY_TIMEOUT = _args.query_timeout if _args.query_timeout is not None else int(os.getenv("QUERY_TIMEOUT", "30"))
    POOL_SIZE = _args.pool_size if _args.pool_size is not None else int(os.getenv("POOL_SIZE", "5"))
    POOL_TIMEOUT = _args.pool_timeout if _args.pool_timeout is not None else int(os.getenv("POOL_TIMEOUT", "30"))

    # Validate and set log level
    raw_log_level = (_args.log_level or os.getenv("LOG_LEVEL", "INFO")).upper()
    if raw_log_level not in _VALID_LOG_LEVELS:
        raw_log_level = "INFO"
        logging.warning("Invalid LOG_LEVEL '%s', falling back to INFO. Valid: %s",
                        _args.log_level or os.getenv("LOG_LEVEL"), ", ".join(sorted(_VALID_LOG_LEVELS)))
    LOG_LEVEL = raw_log_level

    # Security configuration
    _blacklist_raw = _args.blacklist_tables if _args.blacklist_tables is not None else os.getenv("BLACKLIST_TABLES", "")
    BLACKLIST_TABLES = [t.strip() for t in _blacklist_raw.split(",") if t.strip()]
    _schemas_raw = _args.allowed_schemas if _args.allowed_schemas is not None else os.getenv("ALLOWED_SCHEMAS", "")
    ALLOWED_SCHEMAS = [s.strip().lower() for s in _schemas_raw.split(",") if s.strip()]

    # Dictionary configuration
    DICTIONARY_FILE = _args.dictionary_file or os.getenv("DICTIONARY_FILE", "semantic_dictionary.md")

    # Configure logging (after resolving LOG_LEVEL from CLI/env)
    logging.basicConfig(
        level=LOG_LEVEL,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)


# Module-level defaults (overwritten by _load_config at startup)
CONNECTION_STRING: Optional[str] = None
MAX_ROWS = 100
QUERY_TIMEOUT = 30
POOL_SIZE = 5
POOL_TIMEOUT = 30
LOG_LEVEL = "INFO"
BLACKLIST_TABLES: list[str] = []
ALLOWED_SCHEMAS: list[str] = []
DICTIONARY_FILE: str = "semantic_dictionary.md"
logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 4096  # characters
