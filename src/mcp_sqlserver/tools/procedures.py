# -*- coding: utf-8 -*-
"""Tool handler: get_procedures"""

from typing import Any

from mcp.types import TextContent

from mcp_sqlserver.databases import Database


async def handle_get_procedures(db: Database, arguments: dict) -> list[TextContent]:
    """Handle get_procedures tool"""
    schema_filter = arguments.get("schema_filter")
    name_filter = arguments.get("name_filter")
    include_definition = arguments.get("include_definition", False)

    with db.pool.get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT
                s.name AS SchemaName,
                p.name AS ProcedureName,
                p.create_date,
                p.modify_date,
                m.definition AS ProcedureDefinition
            FROM sys.procedures p
            INNER JOIN sys.schemas s ON p.schema_id = s.schema_id
            LEFT JOIN sys.sql_modules m ON p.object_id = m.object_id
            WHERE 1=1
        """
        params: list[Any] = []

        if schema_filter:
            query += " AND s.name = ?"
            params.append(schema_filter)
        if name_filter:
            query += " AND p.name LIKE ?"
            params.append(name_filter.replace("*", "%"))

        query += " ORDER BY s.name, p.name"

        cursor.execute(query, params)
        procedures = cursor.fetchall()

        # Filter by allowed schemas
        filtered = [
            row for row in procedures
            if not db.allowed_schemas or row[0].lower() in db.allowed_schemas
        ]

        if not filtered:
            return [TextContent(type="text", text="# Stored Procedure\n\n*Nessuna stored procedure trovata*")]

        result = "# Stored Procedure\n\n"
        result += f"**Totale:** {len(filtered)}\n\n"

        current_schema = None
        for schema_name, proc_name, create_date, modify_date, definition in filtered:
            if current_schema != schema_name:
                current_schema = schema_name
                result += f"\n## Schema: {schema_name}\n\n"

            result += f"### {schema_name}.{proc_name}\n"
            result += f"*Creata: {create_date:%Y-%m-%d} — Modificata: {modify_date:%Y-%m-%d}*\n\n"

            if include_definition:
                if definition:
                    def_text = definition.strip()
                    if len(def_text) > 3000:
                        def_text = def_text[:3000] + "\n-- ... (troncata, definizione troppo lunga)"
                    result += f"```sql\n{def_text}\n```\n\n"
                else:
                    result += "*(definizione non disponibile — permessi insufficienti o procedura criptata)*\n\n"

        return [TextContent(type="text", text=result)]
