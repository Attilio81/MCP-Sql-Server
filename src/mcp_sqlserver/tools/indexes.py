# -*- coding: utf-8 -*-
"""Tool handler: get_table_indexes"""

from mcp.types import TextContent

from mcp_sqlserver.pool import ConnectionPool
from mcp_sqlserver.security import SecurityValidator


async def handle_table_indexes(pool: ConnectionPool, arguments: dict) -> list[TextContent]:
    """Handle get_table_indexes tool"""
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
        cursor.execute("""
            SELECT
                i.name AS IndexName,
                i.type_desc AS IndexType,
                i.is_unique AS IsUnique,
                i.is_primary_key AS IsPK,
                i.fill_factor AS FillFactor,
                STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS Columns,
                STRING_AGG(
                    CASE WHEN ic.is_included_column = 1 THEN c.name END,
                    ', '
                ) WITHIN GROUP (ORDER BY ic.key_ordinal) AS IncludedColumns
            FROM sys.indexes i
            INNER JOIN sys.index_columns ic
                ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            INNER JOIN sys.columns c
                ON ic.object_id = c.object_id AND ic.column_id = c.column_id
            WHERE i.object_id = OBJECT_ID(? + '.' + ?)
                AND i.name IS NOT NULL
            GROUP BY i.name, i.type_desc, i.is_unique, i.is_primary_key, i.fill_factor
            ORDER BY i.is_primary_key DESC, i.name
        """, (schema, table))

        indexes = cursor.fetchall()

        if not indexes:
            return [TextContent(type="text", text=f"# Indici: {schema}.{table}\n\n*Nessun indice trovato*")]

        result = f"# Indici: {schema}.{table}\n\n"
        result += f"**Totale indici:** {len(indexes)}\n\n"
        result += "| Nome | Tipo | Unico | PK | Fill Factor | Colonne | Colonne Incluse |\n"
        result += "|------|------|-------|----|-----------:|---------|------------------|\n"

        for idx_name, idx_type, is_unique, is_pk, fill_factor, columns, included in indexes:
            unique_str = "✔" if is_unique else "-"
            pk_str = "PK" if is_pk else "-"
            ff_str = str(fill_factor) if fill_factor and fill_factor > 0 else "default"
            included_str = included if included else "-"
            result += f"| {idx_name} | {idx_type} | {unique_str} | {pk_str} | {ff_str} | {columns} | {included_str} |\n"

        return [TextContent(type="text", text=result)]
