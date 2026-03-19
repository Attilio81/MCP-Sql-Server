# -*- coding: utf-8 -*-
"""Tool handler: get_views"""

from typing import Any

from mcp.types import TextContent

from mcp_sqlserver import config
from mcp_sqlserver.pool import ConnectionPool


async def handle_get_views(pool: ConnectionPool, arguments: dict) -> list[TextContent]:
    """Handle get_views tool"""
    schema_filter = arguments.get("schema_filter")
    include_definition = arguments.get("include_definition", True)

    with pool.get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT
                s.name AS SchemaName,
                v.name AS ViewName,
                m.definition AS ViewDefinition
            FROM sys.views v
            INNER JOIN sys.schemas s ON v.schema_id = s.schema_id
            LEFT JOIN sys.sql_modules m ON v.object_id = m.object_id
        """
        params: list[Any] = []

        if schema_filter:
            query += " WHERE s.name = ?"
            params.append(schema_filter)

        query += " ORDER BY s.name, v.name"

        cursor.execute(query, params)
        views = cursor.fetchall()

        if not views:
            return [TextContent(type="text", text="# Viste Database\n\n*Nessuna vista trovata*")]

        # Filter by allowed schemas
        filtered_views = []
        for schema_name, view_name, definition in views:
            if config.ALLOWED_SCHEMAS and schema_name.lower() not in config.ALLOWED_SCHEMAS:
                continue
            filtered_views.append((schema_name, view_name, definition))

        if not filtered_views:
            return [TextContent(type="text", text="# Viste Database\n\n*Nessuna vista accessibile trovata*")]

        result = f"# Viste Database\n\n"
        result += f"**Totale viste:** {len(filtered_views)}\n\n"

        current_schema = None
        for schema_name, view_name, definition in filtered_views:
            if current_schema != schema_name:
                current_schema = schema_name
                result += f"\n## Schema: {schema_name}\n\n"

            result += f"### {schema_name}.{view_name}\n\n"

            if include_definition and definition:
                # Truncate very long definitions
                def_text = definition.strip()
                if len(def_text) > 2000:
                    def_text = def_text[:2000] + "\n-- ... (troncata, definizione troppo lunga)"
                result += f"```sql\n{def_text}\n```\n\n"
            elif not include_definition:
                result += f"*(definizione nascosta)*\n\n"
            else:
                result += f"*(definizione non disponibile — permessi insufficienti)*\n\n"

        return [TextContent(type="text", text=result)]
