# -*- coding: utf-8 -*-
"""Tool handler: list_tables"""

from mcp.types import TextContent

from mcp_sqlserver.pool import ConnectionPool
from mcp_sqlserver.security import SecurityValidator


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
