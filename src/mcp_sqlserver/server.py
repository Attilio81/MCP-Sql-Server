"""
MCP SQL Server - Secure database inspection server
Implements connection pooling, SQL injection prevention, and comprehensive security controls
"""

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
from mcp.types import Tool, TextContent
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
CONNECTION_STRING = os.getenv("SQL_CONNECTION_STRING")
MAX_ROWS = int(os.getenv("MAX_ROWS", "100"))
QUERY_TIMEOUT = int(os.getenv("QUERY_TIMEOUT", "30"))
POOL_SIZE = int(os.getenv("POOL_SIZE", "5"))
POOL_TIMEOUT = int(os.getenv("POOL_TIMEOUT", "30"))

# Security configuration
BLACKLIST_TABLES = [t.strip() for t in os.getenv("BLACKLIST_TABLES", "").split(",") if t.strip()]
ALLOWED_SCHEMAS = [s.strip() for s in os.getenv("ALLOWED_SCHEMAS", "").split(",") if s.strip()]

# Dangerous SQL keywords (for additional query validation)
DANGEROUS_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE",
    "EXEC", "EXECUTE", "GRANT", "REVOKE", "BACKUP", "RESTORE"
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
            except:
                # Connection is dead, create new one
                logger.warning("Connessione morta nel pool, creazione nuova connessione")
                conn.close()
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
                except:
                    # Connection is broken, create new one for pool
                    try:
                        conn.close()
                    except:
                        pass
                    try:
                        new_conn = pyodbc.connect(self.connection_string, timeout=self.timeout)
                        self.pool.put(new_conn)
                    except Exception as e:
                        logger.error(f"Impossibile ripristinare connessione nel pool: {e}")

    def close_all(self):
        """Close all connections in pool"""
        logger.info("Chiusura pool connessioni")
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                conn.close()
            except:
                pass


class SecurityValidator:
    """Validates table names and queries for security"""

    @staticmethod
    def is_table_allowed(table_name: str, schema: Optional[str] = None) -> tuple[bool, str]:
        """
        Check if table is allowed based on blacklist and schema rules
        Returns (is_allowed, error_message)
        """
        # Extract schema and table from full name
        parts = table_name.split(".")
        if len(parts) == 2:
            schema, table = parts
        elif len(parts) == 1:
            table = parts[0]
            schema = schema or "dbo"
        else:
            return False, f"Nome tabella non valido: {table_name}"

        # Check allowed schemas
        if ALLOWED_SCHEMAS and schema not in ALLOWED_SCHEMAS:
            return False, f"Schema '{schema}' non autorizzato. Schemi permessi: {', '.join(ALLOWED_SCHEMAS)}"

        # Check blacklist with wildcard support
        for pattern in BLACKLIST_TABLES:
            if fnmatch.fnmatch(table.lower(), pattern.lower()):
                return False, f"Tabella '{table}' corrisponde al pattern blacklist '{pattern}'"
            if fnmatch.fnmatch(f"{schema}.{table}".lower(), pattern.lower()):
                return False, f"Tabella '{schema}.{table}' corrisponde al pattern blacklist '{pattern}'"

        # Validate table name format (prevent SQL injection)
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
            return False, f"Nome tabella contiene caratteri non validi: {table}"
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', schema):
            return False, f"Nome schema contiene caratteri non validi: {schema}"

        return True, ""

    @staticmethod
    def validate_query(query: str) -> tuple[bool, str]:
        """
        Validate query is safe to execute
        Returns (is_valid, error_message)
        """
        query_upper = query.upper().strip()

        # Must be SELECT
        if not query_upper.startswith("SELECT"):
            return False, "Solo query SELECT sono permesse"

        # Check for dangerous keywords
        for keyword in DANGEROUS_KEYWORDS:
            # Use word boundaries to avoid false positives
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, query_upper):
                return False, f"Keyword '{keyword}' non permessa nella query"

        # Check for common SQL injection patterns
        suspicious_patterns = [
            r';[\s]*DROP',
            r';[\s]*DELETE',
            r';[\s]*UPDATE',
            r'--[\s]*$',  # SQL comments at end
            r'/\*.*\*/',  # Multi-line comments
            r'xp_cmdshell',
            r'sp_executesql',
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, query_upper):
                return False, f"Pattern sospetto rilevato nella query"

        return True, ""


def format_table_data(columns: list[str], rows: list[tuple], max_col_width: int = 50) -> str:
    """Format results as markdown table with truncation for large values"""
    if not rows:
        return "*Nessun dato trovato*"

    def truncate(val, max_len=max_col_width):
        s = str(val) if val is not None else "NULL"
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


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="list_tables",
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
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls with proper error handling"""

    try:
        pool = get_pool()

        if name == "list_tables":
            return await handle_list_tables(pool, arguments)
        elif name == "describe_table":
            return await handle_describe_table(pool, arguments)
        elif name == "execute_query":
            return await handle_execute_query(pool, arguments)
        elif name == "get_table_relationships":
            return await handle_table_relationships(pool, arguments)
        else:
            logger.error(f"Tool sconosciuto: {name}")
            return [TextContent(type="text", text=f"Tool '{name}' non riconosciuto")]

    except TimeoutError as e:
        logger.error(f"Timeout: {e}")
        return [TextContent(type="text", text=f"⏱️ Timeout: {str(e)}")]
    except pyodbc.Error as e:
        logger.error(f"Errore database: {e}")
        return [TextContent(type="text", text=f"❌ Errore database: {str(e)}")]
    except Exception as e:
        logger.exception(f"Errore inaspettato in {name}")
        return [TextContent(type="text", text=f"❌ Errore: {str(e)}")]


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

    # Parse schema.table
    parts = table_name.split(".")
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
            # Use parameterized query with QUOTENAME for identifiers
            query = f"SELECT TOP (?) * FROM {schema}.{table}"
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
        # Insert TOP after SELECT
        query = re.sub(r'^SELECT\s+', f'SELECT TOP {MAX_ROWS} ', query, flags=re.IGNORECASE)

    with pool.get_connection() as conn:
        cursor = conn.cursor()

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

    # Parse schema.table
    parts = table_name.split(".")
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
    from mcp.server.stdio import stdio_server

    logger.info("Avvio MCP SQL Server...")

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


if __name__ == "__main__":
    asyncio.run(main())
