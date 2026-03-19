# -*- coding: utf-8 -*-
"""
MCP SQL Server - Secure database inspection server
Implements connection pooling, SQL injection prevention, and comprehensive security controls
"""

import argparse
import asyncio
import os
import logging
import re
import fnmatch
from typing import Any, Optional
from contextlib import contextmanager
from queue import Queue, Empty
import pyodbc
from mcp.server import Server
from mcp.types import (
    Tool, TextContent, CallToolResult,
    Resource, ResourceTemplate,
    Prompt, PromptArgument, PromptMessage, GetPromptResult,
)
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
    return parser.parse_args()


def _load_config():
    """Load configuration from CLI args and environment variables. Called lazily."""
    global CONNECTION_STRING, MAX_ROWS, QUERY_TIMEOUT, POOL_SIZE, POOL_TIMEOUT
    global LOG_LEVEL, BLACKLIST_TABLES, ALLOWED_SCHEMAS, logger

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
logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 4096  # characters

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


class ConnectionPool:
    """Thread-safe connection pool for SQL Server"""

    def __init__(self, connection_string: str, pool_size: int = 5, timeout: int = 30):
        if not connection_string:
            raise ValueError("SQL_CONNECTION_STRING non configurata")

        self.connection_string = connection_string
        self.pool_size = pool_size
        self.timeout = timeout
        self.pool: Queue = Queue(maxsize=pool_size)

        # Initialize pool
        logger.info(f"Inizializzazione pool connessioni (size={pool_size})")
        for _ in range(pool_size):
            try:
                conn = pyodbc.connect(connection_string, timeout=timeout)
                self.pool.put(conn)
            except Exception as e:
                logger.error(f"Errore creazione connessione nel pool: {e}")
                raise

    @contextmanager
    def get_connection(self):
        """Get connection from pool with automatic return"""
        conn = None
        try:
            conn = self.pool.get(timeout=self.timeout)
            # Verify connection is alive
            try:
                conn.execute("SELECT 1").fetchone()
            except Exception as e:
                # Connection is dead, create new one
                logger.warning("Connessione morta nel pool, creazione nuova connessione: %s", e)
                try:
                    conn.close()
                except Exception as close_err:
                    logger.debug("Errore chiusura connessione morta: %s", close_err)
                conn = pyodbc.connect(self.connection_string, timeout=self.timeout)

            yield conn
        except Empty:
            logger.error("Timeout acquisizione connessione dal pool")
            raise TimeoutError("Pool connessioni esaurito")
        finally:
            if conn:
                try:
                    # Rollback any pending transactions
                    conn.rollback()
                    self.pool.put(conn)
                except Exception as e:
                    logger.warning("Connessione rotta durante il rilascio nel pool: %s", e)
                    # Connection is broken, create new one for pool
                    try:
                        conn.close()
                    except Exception as close_err:
                        logger.debug("Errore chiusura connessione rotta: %s", close_err)
                    try:
                        new_conn = pyodbc.connect(self.connection_string, timeout=self.timeout)
                        self.pool.put(new_conn)
                    except Exception as reconn_err:
                        logger.error(f"Impossibile ripristinare connessione nel pool: {reconn_err}")

    def close_all(self):
        """Close all connections in pool"""
        logger.info("Chiusura pool connessioni")
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                conn.close()
            except Exception as e:
                logger.debug("Errore chiusura connessione durante close_all: %s", e)


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
        if ALLOWED_SCHEMAS and schema.lower() not in ALLOWED_SCHEMAS:
            return False, (
                f"Schema '{schema}' is not authorised. "
                f"Allowed schemas: {', '.join(ALLOWED_SCHEMAS)}"
            )

        # Check blacklist with wildcard support
        for pattern in BLACKLIST_TABLES:
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
        if len(query) > MAX_QUERY_LENGTH:
            return False, (
                f"Query exceeds maximum allowed length "
                f"({len(query)} > {MAX_QUERY_LENGTH} characters)"
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



def format_table_data(columns: list[str], rows: list[tuple], max_col_width: int = 50) -> str:
    """Format results as markdown table with truncation for large values"""
    if not rows:
        return "*Nessun dato trovato*"

    def truncate(val, max_len=max_col_width):
        s = str(val) if val is not None else "NULL"
        s = s.replace("|", "\\|")
        return s if len(s) <= max_len else s[:max_len-3] + "..."

    # Header
    header = "| " + " | ".join(columns) + " |"
    separator = "|" + "|".join(["---" for _ in columns]) + "|"

    # Rows
    data_rows = []
    for row in rows:
        formatted_row = "| " + " | ".join(truncate(val) for val in row) + " |"
        data_rows.append(formatted_row)

    return "\n".join([header, separator] + data_rows)


# Initialize MCP server
app = Server("mcp-sqlserver")

# Initialize connection pool (will be created on first use)
connection_pool: Optional[ConnectionPool] = None


def get_pool() -> ConnectionPool:
    """Get or create connection pool"""
    global connection_pool
    if connection_pool is None:
        connection_pool = ConnectionPool(CONNECTION_STRING, POOL_SIZE, POOL_TIMEOUT)
    return connection_pool


# ------------------------------------------------------------------ #
#  Resources                                                          #
# ------------------------------------------------------------------ #

@app.list_resources()
async def list_resources() -> list[Resource]:
    """List static resources — database schema overview."""
    return [
        Resource(
            uri="db://schema/overview",
            name="database-schema-overview",
            title="Database Schema Overview",
            description="Panoramica completa dello schema del database: tabelle, colonne, tipi e chiavi primarie",
            mimeType="text/plain",
        ),
    ]


@app.list_resource_templates()
async def list_resource_templates() -> list[ResourceTemplate]:
    """List dynamic resource templates for per-table schema inspection."""
    return [
        ResourceTemplate(
            uriTemplate="db://schema/tables/{table_name}",
            name="table-schema",
            title="Table Schema",
            description="Schema dettagliato di una singola tabella (colonne, tipi, chiavi)",
            mimeType="text/plain",
        ),
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read a resource by URI."""
    uri_str = str(uri)

    if uri_str == "db://schema/overview":
        return _read_schema_overview()

    # Match db://schema/tables/{table_name}
    prefix = "db://schema/tables/"
    if uri_str.startswith(prefix):
        table_name = uri_str[len(prefix):]
        if not table_name:
            raise ValueError("Nome tabella mancante nell'URI")
        return _read_table_schema(table_name)

    raise ValueError(f"Risorsa sconosciuta: {uri_str}")


def _read_schema_overview() -> str:
    """Return a full schema overview as plain text."""
    pool = get_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                s.name  AS SchemaName,
                t.name  AS TableName,
                c.name  AS ColumnName,
                tp.name AS DataType,
                c.max_length,
                c.is_nullable,
                CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END AS IsPK
            FROM sys.tables t
            INNER JOIN sys.schemas s    ON t.schema_id  = s.schema_id
            INNER JOIN sys.columns c    ON t.object_id  = c.object_id
            INNER JOIN sys.types   tp   ON c.user_type_id = tp.user_type_id
            LEFT JOIN (
                SELECT ic.object_id, ic.column_id
                FROM sys.index_columns ic
                INNER JOIN sys.indexes i ON ic.object_id = i.object_id
                    AND ic.index_id = i.index_id
                WHERE i.is_primary_key = 1
            ) pk ON c.object_id = pk.object_id AND c.column_id = pk.column_id
            ORDER BY s.name, t.name, c.column_id
        """)
        rows = cursor.fetchall()

    if not rows:
        return "Nessuna tabella trovata nel database."

    lines: list[str] = ["# Database Schema Overview", ""]
    current_table = None
    for schema_name, table_name, col_name, data_type, max_len, nullable, is_pk in rows:
        full_name = f"{schema_name}.{table_name}"

        # Apply access controls
        is_allowed, _ = SecurityValidator.is_table_allowed(full_name)
        if not is_allowed:
            continue

        if full_name != current_table:
            current_table = full_name
            lines.append(f"\n## {full_name}")
            lines.append("| Column | Type | Nullable | PK |")
            lines.append("|--------|------|----------|----|")

        type_str = data_type
        if max_len and max_len > 0 and data_type in ("varchar", "nvarchar", "char", "nchar", "varbinary"):
            type_str += f"({max_len})" if max_len != -1 else "(MAX)"
        nullable_str = "YES" if nullable else "NO"
        pk_str = "PK" if is_pk else "-"
        lines.append(f"| {col_name} | {type_str} | {nullable_str} | {pk_str} |")

    return "\n".join(lines)


def _read_table_schema(table_name: str) -> str:
    """Return the schema for a single table."""
    # Security validation
    is_allowed, error_msg = SecurityValidator.is_table_allowed(table_name)
    if not is_allowed:
        raise ValueError(f"Accesso negato: {error_msg}")

    parts = [SecurityValidator._strip_brackets(p) for p in table_name.split(".")]
    if len(parts) == 2:
        schema, table = parts
    else:
        schema, table = "dbo", parts[0]

    pool = get_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.CHARACTER_MAXIMUM_LENGTH,
                c.NUMERIC_PRECISION,
                c.NUMERIC_SCALE,
                c.IS_NULLABLE,
                c.COLUMN_DEFAULT,
                CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 'PK' ELSE '' END as KeyType
            FROM INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN (
                SELECT ku.TABLE_SCHEMA, ku.TABLE_NAME, ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ) pk ON c.TABLE_SCHEMA = pk.TABLE_SCHEMA
                AND c.TABLE_NAME = pk.TABLE_NAME
                AND c.COLUMN_NAME = pk.COLUMN_NAME
            WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ?
            ORDER BY c.ORDINAL_POSITION
        """, (schema, table))
        columns_info = cursor.fetchall()

    if not columns_info:
        raise ValueError(f"Tabella '{schema}.{table}' non trovata")

    lines: list[str] = [
        f"# Schema: {schema}.{table}",
        "",
        "| Column | Type | Nullable | Key | Default |",
        "|--------|------|----------|-----|---------|",
    ]
    for col_name, data_type, max_len, num_prec, num_scale, nullable, default, key_type in columns_info:
        type_str = data_type
        if max_len and max_len > 0:
            type_str += f"({max_len})"
        elif num_prec:
            if num_scale:
                type_str += f"({num_prec},{num_scale})"
            else:
                type_str += f"({num_prec})"
        default_str = default if default else "-"
        key_str = key_type if key_type else "-"
        lines.append(f"| {col_name} | {type_str} | {nullable} | {key_str} | {default_str} |")

    return "\n".join(lines)


# ------------------------------------------------------------------ #
#  Prompts                                                            #
# ------------------------------------------------------------------ #

@app.list_prompts()
async def list_prompts() -> list[Prompt]:
    """List available prompt templates."""
    return [
        Prompt(
            name="analyze-table",
            title="Analyze Table",
            description="Analizza la struttura di una tabella e suggerisce osservazioni su schema, tipi e relazioni",
            arguments=[
                PromptArgument(
                    name="table_name",
                    description="Nome della tabella (formato: schema.table o solo table per dbo)",
                    required=True,
                ),
            ],
        ),
        Prompt(
            name="query-builder",
            title="Query Builder",
            description="Aiuta a costruire una query SELECT a partire da una descrizione in linguaggio naturale",
            arguments=[
                PromptArgument(
                    name="description",
                    description="Descrizione in linguaggio naturale di cosa cercare (es. 'ordini del 2026 raggruppati per mese')",
                    required=True,
                ),
                PromptArgument(
                    name="tables",
                    description="Tabelle coinvolte, separate da virgola (es. 'Orders,Customers')",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="data-dictionary",
            title="Data Dictionary",
            description="Genera un data dictionary completo per una o più tabelle del database",
            arguments=[
                PromptArgument(
                    name="tables",
                    description="Tabelle da documentare, separate da virgola (vuoto = tutte le tabelle accessibili)",
                    required=False,
                ),
            ],
        ),
    ]


@app.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
    """Return a prompt by name with filled arguments."""
    arguments = arguments or {}

    if name == "analyze-table":
        table_name = arguments.get("table_name", "")
        if not table_name:
            raise ValueError("Argomento 'table_name' richiesto")
        return GetPromptResult(
            description=f"Analisi della tabella {table_name}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Analizza la tabella '{table_name}' nel database SQL Server.\n\n"
                            "Per favore:\n"
                            "1. Usa il tool 'describe_table' per ottenere lo schema completo\n"
                            "2. Usa il tool 'get_table_relationships' per vedere le relazioni\n"
                            "3. Usa il tool 'execute_query' per un conteggio righe e statistiche base\n\n"
                            "Poi fornisci:\n"
                            "- Panoramica della struttura della tabella\n"
                            "- Osservazioni sui tipi di dato scelti\n"
                            "- Analisi delle relazioni con altre tabelle\n"
                            "- Eventuali suggerimenti per miglioramenti allo schema"
                        ),
                    ),
                ),
            ],
        )

    elif name == "query-builder":
        description = arguments.get("description", "")
        if not description:
            raise ValueError("Argomento 'description' richiesto")
        tables = arguments.get("tables", "")
        tables_hint = f"\nTabelle da usare: {tables}" if tables else ""
        return GetPromptResult(
            description=f"Costruzione query: {description}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Ho bisogno di una query SQL Server per: {description}\n"
                            f"{tables_hint}\n\n"
                            "Per favore:\n"
                            "1. Usa 'list_tables' per vedere le tabelle disponibili\n"
                            "2. Usa 'describe_table' per capire la struttura delle tabelle rilevanti\n"
                            "3. Costruisci una query SELECT ottimizzata\n"
                            "4. Eseguila con 'execute_query' e mostra i risultati\n\n"
                            "Ricorda: solo query SELECT sono permesse. "
                            "Usa JOIN dove necessario e alias chiari per le colonne."
                        ),
                    ),
                ),
            ],
        )

    elif name == "data-dictionary":
        tables = arguments.get("tables", "")
        if tables:
            scope = f"le tabelle: {tables}"
        else:
            scope = "tutte le tabelle accessibili"
        return GetPromptResult(
            description=f"Data dictionary per {scope}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Genera un data dictionary completo per {scope} nel database.\n\n"
                            "Per favore:\n"
                            "1. Usa 'list_tables' per elencare le tabelle\n"
                            "2. Per ogni tabella, usa 'describe_table' per ottenere lo schema\n"
                            "3. Usa 'get_table_relationships' per le relazioni\n\n"
                            "Per ogni tabella, documenta:\n"
                            "- Nome e scopo presunto della tabella\n"
                            "- Elenco colonne con tipo, nullable, chiave e descrizione stimata\n"
                            "- Relazioni (FK in entrata e in uscita)\n"
                            "- Conteggio righe approssimativo\n\n"
                            "Formatta il risultato in Markdown strutturato, pronto per la documentazione."
                        ),
                    ),
                ),
            ],
        )

    raise ValueError(f"Prompt sconosciuto: {name}")


# ------------------------------------------------------------------ #
#  Tools                                                              #
# ------------------------------------------------------------------ #

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="list_tables",
            title="List Tables",
            description="Elenca tutte le tabelle accessibili del database con conteggio righe e informazioni schema",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema_filter": {
                        "type": "string",
                        "description": "Filtra per schema specifico (opzionale)",
                    }
                },
            },
        ),
        Tool(
            name="describe_table",
            title="Describe Table",
            description="Mostra schema completo di una tabella (colonne, tipi, constraints) con opzionali righe di esempio",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Nome della tabella (formato: schema.table o solo table per dbo)",
                    },
                    "sample_rows": {
                        "type": "integer",
                        "description": "Numero di righe di esempio (default: 10, max: 50)",
                        "default": 10,
                        "minimum": 0,
                        "maximum": 50,
                    },
                },
                "required": ["table_name"],
            },
        ),
        Tool(
            name="execute_query",
            title="Execute Query",
            description=f"Esegue una query SELECT sul database (max {MAX_ROWS} righe, timeout {QUERY_TIMEOUT}s). Solo SELECT permesso.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query SQL SELECT da eseguire",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_table_relationships",
            title="Get Table Relationships",
            description="Mostra le relazioni (foreign keys) di una tabella con altre tabelle",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Nome della tabella (formato: schema.table o solo table per dbo)",
                    },
                },
                "required": ["table_name"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> CallToolResult:
    """Handle tool calls with proper error handling"""

    try:
        pool = get_pool()

        if name == "list_tables":
            content = await handle_list_tables(pool, arguments)
        elif name == "describe_table":
            content = await handle_describe_table(pool, arguments)
        elif name == "execute_query":
            content = await handle_execute_query(pool, arguments)
        elif name == "get_table_relationships":
            content = await handle_table_relationships(pool, arguments)
        else:
            logger.error(f"Tool sconosciuto: {name}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Tool '{name}' non riconosciuto")],
                isError=True,
            )

        return CallToolResult(content=content, isError=False)

    except TimeoutError as e:
        logger.error(f"Timeout: {e}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"⏱️ Timeout: {str(e)}")],
            isError=True,
        )
    except pyodbc.Error as e:
        logger.error(f"Errore database: {e}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ Errore database: {str(e)}")],
            isError=True,
        )
    except Exception as e:
        logger.exception(f"Errore inaspettato in {name}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ Errore: {str(e)}")],
            isError=True,
        )


async def handle_list_tables(pool: ConnectionPool, arguments: dict) -> list[TextContent]:
    """Handle list_tables tool"""
    schema_filter = arguments.get("schema_filter")

    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # Build query with parameterized schema filter
        query = """
            SELECT
                s.name as SchemaName,
                t.name as TableName,
                p.rows as RowCount,
                CAST(SUM(a.total_pages) * 8 / 1024.0 AS DECIMAL(10,2)) as SizeMB
            FROM sys.tables t
            INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
            INNER JOIN sys.partitions p ON t.object_id = p.object_id
            INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
            WHERE p.index_id IN (0,1)
        """

        params = []
        if schema_filter:
            query += " AND s.name = ?"
            params.append(schema_filter)

        query += """
            GROUP BY s.name, t.name, p.rows
            ORDER BY s.name, t.name
        """

        cursor.execute(query, params)
        tables = cursor.fetchall()

        result = f"# Database Tables\n\n"
        result += f"**Totale tabelle trovate:** {len(tables)}\n\n"

        if not tables:
            result += "*Nessuna tabella trovata*\n"
            return [TextContent(type="text", text=result)]

        # Group by schema
        current_schema = None
        accessible_count = 0
        blocked_count = 0

        for schema_name, table_name, row_count, size_mb in tables:
            full_name = f"{schema_name}.{table_name}"
            is_allowed, error_msg = SecurityValidator.is_table_allowed(full_name)

            if current_schema != schema_name:
                current_schema = schema_name
                result += f"\n## Schema: {schema_name}\n\n"

            if is_allowed:
                result += f"- **{table_name}** ({row_count:,} righe, {size_mb:.2f} MB)\n"
                accessible_count += 1
            else:
                result += f"- ~~{table_name}~~ 🔒 *{error_msg}*\n"
                blocked_count += 1

        result += f"\n---\n**Accessibili:** {accessible_count} | **Bloccate:** {blocked_count}\n"

        return [TextContent(type="text", text=result)]


async def handle_describe_table(pool: ConnectionPool, arguments: dict) -> list[TextContent]:
    """Handle describe_table tool"""
    table_name = arguments["table_name"].strip()
    sample_rows = min(max(arguments.get("sample_rows", 10), 0), 50)

    # Security validation
    is_allowed, error_msg = SecurityValidator.is_table_allowed(table_name)
    if not is_allowed:
        return [TextContent(type="text", text=f"🔒 Accesso negato: {error_msg}")]

    # Parse schema.table — strip optional bracket quoting ([dbo].[MyTable])
    parts = [SecurityValidator._strip_brackets(p) for p in table_name.split(".")]
    if len(parts) == 2:
        schema, table = parts
    else:
        schema, table = "dbo", parts[0]

    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # Get table schema information
        cursor.execute("""
            SELECT
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.CHARACTER_MAXIMUM_LENGTH,
                c.NUMERIC_PRECISION,
                c.NUMERIC_SCALE,
                c.IS_NULLABLE,
                c.COLUMN_DEFAULT,
                CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 'PK' ELSE '' END as KeyType
            FROM INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN (
                SELECT ku.TABLE_SCHEMA, ku.TABLE_NAME, ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ) pk ON c.TABLE_SCHEMA = pk.TABLE_SCHEMA
                AND c.TABLE_NAME = pk.TABLE_NAME
                AND c.COLUMN_NAME = pk.COLUMN_NAME
            WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ?
            ORDER BY c.ORDINAL_POSITION
        """, (schema, table))

        columns_info = cursor.fetchall()

        if not columns_info:
            return [TextContent(type="text", text=f"❌ Tabella '{schema}.{table}' non trovata")]

        result = f"# Schema: {schema}.{table}\n\n"
        result += "| Colonna | Tipo | Nullable | Key | Default |\n"
        result += "|---------|------|----------|-----|----------|\n"

        for col_name, data_type, max_len, num_prec, num_scale, nullable, default, key_type in columns_info:
            # Format type
            type_str = data_type
            if max_len and max_len > 0:
                type_str += f"({max_len})"
            elif num_prec:
                if num_scale:
                    type_str += f"({num_prec},{num_scale})"
                else:
                    type_str += f"({num_prec})"

            default_str = default if default else "-"
            key_str = key_type if key_type else "-"

            result += f"| {col_name} | {type_str} | {nullable} | {key_str} | {default_str} |\n"

        # Get sample data if requested
        if sample_rows > 0:
            # schema and table have been validated against ^[a-zA-Z_][a-zA-Z0-9_]*$ above;
            # it is safe to interpolate them as identifiers.
            query = f"SELECT TOP (?) * FROM [{schema}].[{table}]"
            cursor.execute(query, (sample_rows,))
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()

            result += f"\n## Dati di esempio (prime {len(rows)} righe)\n\n"
            result += format_table_data(columns, rows)

        return [TextContent(type="text", text=result)]


async def handle_execute_query(pool: ConnectionPool, arguments: dict) -> list[TextContent]:
    """Handle execute_query tool"""
    query = arguments["query"].strip()

    # Security validation
    is_valid, error_msg = SecurityValidator.validate_query(query)
    if not is_valid:
        return [TextContent(type="text", text=f"🔒 Query non valida: {error_msg}")]

    # Add TOP clause if not present
    query_upper = query.upper()
    if "TOP" not in query_upper and "TOP(" not in query_upper:
        # Insert TOP after SELECT, respecting DISTINCT / ALL keywords
        query = re.sub(
            r'^SELECT\s+(DISTINCT\s+|ALL\s+)?',
            lambda m: f'SELECT {(m.group(1) or "").strip()} TOP {MAX_ROWS} '.replace("  ", " "),
            query,
            count=1,
            flags=re.IGNORECASE,
        )

    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.timeout = QUERY_TIMEOUT
        # Enforce read-only isolation — prevents dirty reads and any accidental writes
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")

        logger.info(f"Executing query: {query[:100]}...")
        cursor.execute(query)

        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()

        result = f"# Risultati Query\n\n"
        result += f"```sql\n{query}\n```\n\n"
        result += f"**Righe restituite:** {len(rows)}\n"

        if len(rows) >= MAX_ROWS:
            result += f"⚠️ *Risultato limitato a {MAX_ROWS} righe*\n"

        result += "\n" + format_table_data(columns, rows)

        return [TextContent(type="text", text=result)]


async def handle_table_relationships(pool: ConnectionPool, arguments: dict) -> list[TextContent]:
    """Handle get_table_relationships tool"""
    table_name = arguments["table_name"].strip()

    # Security validation
    is_allowed, error_msg = SecurityValidator.is_table_allowed(table_name)
    if not is_allowed:
        return [TextContent(type="text", text=f"🔒 Accesso negato: {error_msg}")]

    # Parse schema.table — strip optional bracket quoting ([dbo].[MyTable])
    parts = [SecurityValidator._strip_brackets(p) for p in table_name.split(".")]
    if len(parts) == 2:
        schema, table = parts
    else:
        schema, table = "dbo", parts[0]

    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # Get foreign key relationships
        cursor.execute("""
            SELECT
                fk.name as FK_Name,
                OBJECT_SCHEMA_NAME(fk.parent_object_id) as FromSchema,
                OBJECT_NAME(fk.parent_object_id) as FromTable,
                COL_NAME(fkc.parent_object_id, fkc.parent_column_id) as FromColumn,
                OBJECT_SCHEMA_NAME(fk.referenced_object_id) as ToSchema,
                OBJECT_NAME(fk.referenced_object_id) as ToTable,
                COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) as ToColumn
            FROM sys.foreign_keys fk
            INNER JOIN sys.foreign_key_columns fkc
                ON fk.object_id = fkc.constraint_object_id
            WHERE
                (OBJECT_SCHEMA_NAME(fk.parent_object_id) = ? AND OBJECT_NAME(fk.parent_object_id) = ?)
                OR
                (OBJECT_SCHEMA_NAME(fk.referenced_object_id) = ? AND OBJECT_NAME(fk.referenced_object_id) = ?)
            ORDER BY fk.name
        """, (schema, table, schema, table))

        relationships = cursor.fetchall()

        if not relationships:
            return [TextContent(type="text", text=f"# Relazioni: {schema}.{table}\n\n*Nessuna foreign key trovata*")]

        result = f"# Relazioni: {schema}.{table}\n\n"
        result += f"**Totale relazioni:** {len(relationships)}\n\n"

        # Separate outgoing and incoming relationships
        outgoing = []
        incoming = []

        for rel in relationships:
            fk_name, from_schema, from_table, from_col, to_schema, to_table, to_col = rel
            if from_schema == schema and from_table == table:
                outgoing.append((fk_name, from_col, to_schema, to_table, to_col))
            else:
                incoming.append((fk_name, from_schema, from_table, from_col, to_col))

        if outgoing:
            result += "## Relazioni in uscita (questa tabella referenzia:)\n\n"
            for fk_name, from_col, to_schema, to_table, to_col in outgoing:
                result += f"- **{from_col}** → {to_schema}.{to_table}.{to_col} `[{fk_name}]`\n"

        if incoming:
            result += "\n## Relazioni in entrata (altre tabelle referenziano questa:)\n\n"
            for fk_name, from_schema, from_table, from_col, to_col in incoming:
                result += f"- {from_schema}.{from_table}.{from_col} → **{to_col}** `[{fk_name}]`\n"

        return [TextContent(type="text", text=result)]


async def main():
    """Entry point"""
    _load_config()

    from mcp.server.stdio import stdio_server

    logger.info("Avvio MCP SQL Server...")

    if not CONNECTION_STRING:
        logger.error("SQL_CONNECTION_STRING non configurata. Imposta la variabile d'ambiente o usa --connection-string.")
        return

    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
    finally:
        # Cleanup connection pool
        if connection_pool:
            connection_pool.close_all()
        logger.info("MCP SQL Server terminato")


def run():
    """Synchronous entry point for console_scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
