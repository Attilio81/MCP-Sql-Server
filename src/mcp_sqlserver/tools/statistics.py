# -*- coding: utf-8 -*-
"""Tool handler: get_table_statistics"""

from mcp.types import TextContent

from mcp_sqlserver import config
from mcp_sqlserver.pool import ConnectionPool
from mcp_sqlserver.security import SecurityValidator


async def handle_table_statistics(pool: ConnectionPool, arguments: dict) -> list[TextContent]:
    """Handle get_table_statistics tool"""
    table_name = arguments["table_name"].strip()

    # Security validation
    is_allowed, error_msg = SecurityValidator.is_table_allowed(table_name)
    if not is_allowed:
        return [TextContent(type="text", text=f"🔒 Accesso negato: {error_msg}")]

    # Parse schema.table
    parts = [SecurityValidator._strip_brackets(p) for p in table_name.split(".")]
    if len(parts) == 2:
        schema, table = parts
    else:
        schema, table = "dbo", parts[0]

    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # Get column info first
        cursor.execute("""
            SELECT c.name, tp.name AS data_type
            FROM sys.columns c
            INNER JOIN sys.types tp ON c.user_type_id = tp.user_type_id
            WHERE c.object_id = OBJECT_ID(? + '.' + ?)
            ORDER BY c.column_id
        """, (schema, table))
        columns_info = cursor.fetchall()

        if not columns_info:
            return [TextContent(type="text", text=f"❌ Tabella '{schema}.{table}' non trovata")]

        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM [{schema}].[{table}]")
        total_rows = cursor.fetchone()[0]

        # Numeric and date types for which min/max makes sense
        stat_types = {
            "int", "bigint", "smallint", "tinyint", "decimal", "numeric",
            "float", "real", "money", "smallmoney",
            "date", "datetime", "datetime2", "smalldatetime", "datetimeoffset", "time",
        }

        # Build per-column stats query dynamically
        # schema and table have been validated against _IDENTIFIER_RE
        stat_parts = []
        for col_name, data_type in columns_info:
            # col_name is validated indirectly (comes from sys.columns)
            escaped_col = col_name.replace("'", "''")
            stat_parts.append(
                f"SELECT "
                f"'{escaped_col}' AS col_name, "
                f"COUNT(DISTINCT [{col_name}]) AS distinct_count, "
                f"SUM(CASE WHEN [{col_name}] IS NULL THEN 1 ELSE 0 END) AS null_count"
                + (f", MIN([{col_name}]) AS min_val, MAX([{col_name}]) AS max_val"
                   if data_type in stat_types else ", NULL AS min_val, NULL AS max_val")
                + f" FROM [{schema}].[{table}]"
            )

        full_query = " UNION ALL ".join(stat_parts)
        cursor.timeout = config.QUERY_TIMEOUT
        cursor.execute(full_query)
        stats_rows = cursor.fetchall()

        result = f"# Statistiche: {schema}.{table}\n\n"
        result += f"**Righe totali:** {total_rows:,}\n\n"
        result += "| Colonna | Tipo | Valori Distinti | NULL | Min | Max |\n"
        result += "|---------|------|----------------:|-----:|-----|-----|\n"

        col_type_map = {name: dtype for name, dtype in columns_info}
        for col_name, distinct_count, null_count, min_val, max_val in stats_rows:
            data_type = col_type_map.get(col_name, "?")
            min_str = str(min_val) if min_val is not None else "-"
            max_str = str(max_val) if max_val is not None else "-"
            result += f"| {col_name} | {data_type} | {distinct_count:,} | {null_count:,} | {min_str} | {max_str} |\n"

        return [TextContent(type="text", text=result)]
