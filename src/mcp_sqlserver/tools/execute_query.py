# -*- coding: utf-8 -*-
"""Tool handler: execute_query"""

import re
import logging

from mcp.types import TextContent

from mcp_sqlserver import config
from mcp_sqlserver.pool import ConnectionPool
from mcp_sqlserver.security import SecurityValidator
from mcp_sqlserver.helpers import format_table_data

logger = logging.getLogger(__name__)


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
            lambda m: f'SELECT {(m.group(1) or "").strip()} TOP {config.MAX_ROWS} '.replace("  ", " "),
            query,
            count=1,
            flags=re.IGNORECASE,
        )

    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.timeout = config.QUERY_TIMEOUT
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

        result += "\n" + format_table_data(columns, rows)

        return [TextContent(type="text", text=result)]
