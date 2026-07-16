# -*- coding: utf-8 -*-
"""Tool handler: execute_query"""

import re
import logging

from mcp.types import TextContent

from mcp_sqlserver import config
from mcp_sqlserver.pool import ConnectionPool
from mcp_sqlserver.security import SecurityValidator
from mcp_sqlserver.helpers import format_table_data, format_csv, format_json

logger = logging.getLogger(__name__)


def ensure_top(query: str, max_rows: int) -> str:
    """Add a TOP clause after SELECT if the query has none."""
    if re.search(r'\bTOP\b', query, re.IGNORECASE):
        return query
    # Insert TOP after SELECT, respecting DISTINCT / ALL keywords
    return re.sub(
        r'^SELECT\s+(DISTINCT\s+|ALL\s+)?',
        lambda m: f'SELECT {(m.group(1) or "").strip()} TOP {max_rows} '.replace("  ", " "),
        query,
        count=1,
        flags=re.IGNORECASE,
    )


async def handle_execute_query(pool: ConnectionPool, arguments: dict) -> list[TextContent]:
    """Handle execute_query tool"""
    query = arguments["query"].strip()
    output_format = arguments.get("format", "markdown")

    # Security validation
    is_valid, error_msg = SecurityValidator.validate_query(query)
    if not is_valid:
        return [TextContent(type="text", text=f"🔒 Query non valida: {error_msg}")]

    # Enforce blacklist / schema whitelist on every table referenced in the query
    for table in SecurityValidator.extract_table_names(query):
        allowed, error_msg = SecurityValidator.is_table_allowed(table)
        if not allowed:
            return [TextContent(type="text", text=f"🔒 Query non valida: {error_msg}")]

    query = ensure_top(query, config.MAX_ROWS)

    with pool.get_connection() as conn:
        conn.timeout = config.QUERY_TIMEOUT
        cursor = conn.cursor()
        # Enforce read-only isolation — prevents dirty reads and any accidental writes
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")

        logger.info(f"Executing query: {query[:100]}...")
        cursor.execute(query)

        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()

        result = f"# Risultati Query\n\n"
        result += f"```sql\n{query}\n```\n\n"
        result += f"**Righe restituite:** {len(rows)}\n"

        if len(rows) >= config.MAX_ROWS:
            result += f"⚠️ *Risultato limitato a {config.MAX_ROWS} righe*\n"

        if output_format == "csv":
            result += "\n" + format_csv(columns, rows)
        elif output_format == "json":
            result += "\n" + format_json(columns, rows)
        else:
            result += "\n" + format_table_data(columns, rows)

        return [TextContent(type="text", text=result)]
