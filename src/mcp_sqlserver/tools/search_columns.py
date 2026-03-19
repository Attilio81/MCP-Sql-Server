# -*- coding: utf-8 -*-
"""Tool handler: search_columns"""

from typing import Any

from mcp.types import TextContent

from mcp_sqlserver.pool import ConnectionPool
from mcp_sqlserver.security import SecurityValidator


async def handle_search_columns(pool: ConnectionPool, arguments: dict) -> list[TextContent]:
    """Handle search_columns tool"""
    column_pattern = arguments["column_pattern"].strip()
    schema_filter = arguments.get("schema_filter")

    # Convert wildcard pattern to SQL LIKE pattern
    like_pattern = column_pattern.replace("*", "%").replace("?", "_")
    # If no wildcards were provided, do a contains search
    if "%" not in like_pattern and "_" not in like_pattern:
        like_pattern = f"%{like_pattern}%"

    with pool.get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT
                s.name AS SchemaName,
                t.name AS TableName,
                c.name AS ColumnName,
                tp.name AS DataType,
                c.max_length,
                c.is_nullable,
                CASE WHEN pk.column_id IS NOT NULL THEN 'PK' ELSE '' END AS IsPK
            FROM sys.tables t
            INNER JOIN sys.schemas s    ON t.schema_id = s.schema_id
            INNER JOIN sys.columns c    ON t.object_id = c.object_id
            INNER JOIN sys.types   tp   ON c.user_type_id = tp.user_type_id
            LEFT JOIN (
                SELECT ic.object_id, ic.column_id
                FROM sys.index_columns ic
                INNER JOIN sys.indexes i ON ic.object_id = i.object_id
                    AND ic.index_id = i.index_id
                WHERE i.is_primary_key = 1
            ) pk ON c.object_id = pk.object_id AND c.column_id = pk.column_id
            WHERE c.name LIKE ?
        """
        params: list[Any] = [like_pattern]

        if schema_filter:
            query += " AND s.name = ?"
            params.append(schema_filter)

        query += " ORDER BY s.name, t.name, c.column_id"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        if not rows:
            return [TextContent(type="text", text=f"# Ricerca Colonne: `{column_pattern}`\n\n*Nessun risultato trovato*")]

        # Filter out blacklisted tables
        filtered_rows = []
        for row in rows:
            schema_name, table_name_val = row[0], row[1]
            full_name = f"{schema_name}.{table_name_val}"
            is_allowed, _ = SecurityValidator.is_table_allowed(full_name)
            if is_allowed:
                filtered_rows.append(row)

        if not filtered_rows:
            return [TextContent(type="text", text=f"# Ricerca Colonne: `{column_pattern}`\n\n*Nessun risultato trovato (tabelle corrispondenti sono bloccate)*")]

        result = f"# Ricerca Colonne: `{column_pattern}`\n\n"
        result += f"**Risultati trovati:** {len(filtered_rows)}\n\n"
        result += "| Schema | Tabella | Colonna | Tipo | Nullable | PK |\n"
        result += "|--------|---------|---------|------|----------|----|\n"

        for schema_name, table_name_val, col_name, data_type, max_len, nullable, is_pk in filtered_rows:
            type_str = data_type
            if max_len and max_len > 0 and data_type in ("varchar", "nvarchar", "char", "nchar", "varbinary"):
                type_str += f"({max_len})" if max_len != -1 else "(MAX)"
            nullable_str = "YES" if nullable else "NO"
            pk_str = is_pk if is_pk else "-"
            result += f"| {schema_name} | {table_name_val} | {col_name} | {type_str} | {nullable_str} | {pk_str} |\n"

        return [TextContent(type="text", text=result)]
