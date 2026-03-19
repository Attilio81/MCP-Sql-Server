# -*- coding: utf-8 -*-
"""Tool handler: get_table_relationships"""

from mcp.types import TextContent

from mcp_sqlserver.pool import ConnectionPool
from mcp_sqlserver.security import SecurityValidator


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
