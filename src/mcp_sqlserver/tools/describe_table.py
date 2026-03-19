# -*- coding: utf-8 -*-
"""Tool handler: describe_table"""

from mcp.types import TextContent

from mcp_sqlserver.pool import ConnectionPool
from mcp_sqlserver.security import SecurityValidator
from mcp_sqlserver.helpers import format_table_data


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
