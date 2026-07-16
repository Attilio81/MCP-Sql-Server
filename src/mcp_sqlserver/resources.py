# -*- coding: utf-8 -*-
"""
MCP Resources for SQL Server database schema inspection.

URIs are per-database: db://{name}/schema/overview, db://{name}/dictionary,
db://{name}/schema/tables/{table}. In single-database mode the legacy
unnamed URIs (db://schema/overview, db://dictionary, db://schema/tables/{t})
keep working as aliases for the only configured database.
"""

import asyncio
from pathlib import Path

from mcp.types import Resource, ResourceTemplate

from mcp_sqlserver import databases
from mcp_sqlserver.databases import Database
from mcp_sqlserver.security import SecurityValidator


def register_resources(app):
    """Register all resource handlers on the MCP app."""

    @app.list_resources()
    async def list_resources() -> list[Resource]:
        """Per-database schema overview and semantic dictionary."""
        multi = databases.is_multi()
        resources: list[Resource] = []
        for name in sorted(databases.DATABASES):
            prefix = f"db://{name}" if multi else "db:/"
            label = f" [{name}]" if multi else ""
            resources.append(Resource(
                uri=f"{prefix}/schema/overview",
                name=f"database-schema-overview{('-' + name) if multi else ''}",
                title=f"Database Schema Overview{label}",
                description=f"Panoramica completa dello schema{label}: tabelle, colonne, tipi e chiavi primarie",
                mimeType="text/plain",
            ))
            resources.append(Resource(
                uri=f"{prefix}/dictionary",
                name=f"semantic-dictionary{('-' + name) if multi else ''}",
                title=f"Semantic Dictionary{label}",
                description=(
                    f"Dizionario semantico{label}: mappa tra linguaggio di business e schema fisico. "
                    "Carica questa risorsa all'inizio della sessione per conoscere le associazioni già scoperte."
                ),
                mimeType="text/markdown",
            ))
        return resources

    @app.list_resource_templates()
    async def list_resource_templates() -> list[ResourceTemplate]:
        if databases.is_multi():
            template = "db://{database}/schema/tables/{table_name}"
        else:
            template = "db://schema/tables/{table_name}"
        return [
            ResourceTemplate(
                uriTemplate=template,
                name="table-schema",
                title="Table Schema",
                description="Schema dettagliato di una singola tabella (colonne, tipi, chiavi)",
                mimeType="text/plain",
            ),
        ]

    @app.read_resource()
    async def read_resource(uri: str) -> str:
        """Read a resource by URI (named or legacy single-db form)."""
        uri_str = str(uri)
        if not uri_str.startswith("db://"):
            raise ValueError(f"Risorsa sconosciuta: {uri_str}")
        path = uri_str[len("db://"):]

        # Legacy unnamed URIs → the only configured database
        if path in ("schema/overview", "dictionary") or path.startswith("schema/tables/"):
            db = databases.get_database()  # raises if ambiguous (multi-db)
        else:
            name, _, path = path.partition("/")
            db = databases.get_database(name)

        # Blocking pyodbc work runs in a worker thread (same as tool handlers)
        if path == "schema/overview":
            return await asyncio.to_thread(_read_schema_overview, db)
        if path == "dictionary":
            return await asyncio.to_thread(_read_dictionary, db)
        prefix = "schema/tables/"
        if path.startswith(prefix):
            table_name = path[len(prefix):]
            if not table_name:
                raise ValueError("Nome tabella mancante nell'URI")
            return await asyncio.to_thread(_read_table_schema, db, table_name)

        raise ValueError(f"Risorsa sconosciuta: {uri_str}")


def _read_schema_overview(db: Database) -> str:
    """Return a full schema overview as plain text."""
    with db.pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                s.name  AS SchemaName,
                t.name  AS TableName,
                c.name  AS ColumnName,
                tp.name AS DataType,
                c.max_length,
                c.is_nullable,
                CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END AS IsPK
            FROM sys.tables t
            INNER JOIN sys.schemas s    ON t.schema_id  = s.schema_id
            INNER JOIN sys.columns c    ON t.object_id  = c.object_id
            INNER JOIN sys.types   tp   ON c.user_type_id = tp.user_type_id
            LEFT JOIN (
                SELECT ic.object_id, ic.column_id
                FROM sys.index_columns ic
                INNER JOIN sys.indexes i ON ic.object_id = i.object_id
                    AND ic.index_id = i.index_id
                WHERE i.is_primary_key = 1
            ) pk ON c.object_id = pk.object_id AND c.column_id = pk.column_id
            ORDER BY s.name, t.name, c.column_id
        """)
        rows = cursor.fetchall()

    if not rows:
        return "Nessuna tabella trovata nel database."

    lines: list[str] = ["# Database Schema Overview", ""]
    current_table = None
    for schema_name, table_name, col_name, data_type, max_len, nullable, is_pk in rows:
        full_name = f"{schema_name}.{table_name}"

        # Apply access controls
        is_allowed, _ = SecurityValidator.is_table_allowed(
            full_name, allowed_schemas=db.allowed_schemas, blacklist=db.blacklist_tables)
        if not is_allowed:
            continue

        if full_name != current_table:
            current_table = full_name
            lines.append(f"\n## {full_name}")
            lines.append("| Column | Type | Nullable | PK |")
            lines.append("|--------|------|----------|----|")

        type_str = data_type
        if max_len and max_len > 0 and data_type in ("varchar", "nvarchar", "char", "nchar", "varbinary"):
            type_str += f"({max_len})" if max_len != -1 else "(MAX)"
        nullable_str = "YES" if nullable else "NO"
        pk_str = "PK" if is_pk else "-"
        lines.append(f"| {col_name} | {type_str} | {nullable_str} | {pk_str} |")

    return "\n".join(lines)


def _read_table_schema(db: Database, table_name: str) -> str:
    """Return the schema for a single table."""
    # Security validation
    is_allowed, error_msg = SecurityValidator.is_table_allowed(
        table_name, allowed_schemas=db.allowed_schemas, blacklist=db.blacklist_tables)
    if not is_allowed:
        raise ValueError(f"Accesso negato: {error_msg}")

    parts = [SecurityValidator._strip_brackets(p) for p in table_name.split(".")]
    if len(parts) == 2:
        schema, table = parts
    else:
        schema, table = "dbo", parts[0]

    with db.pool.get_connection() as conn:
        cursor = conn.cursor()
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
        raise ValueError(f"Tabella '{schema}.{table}' non trovata")

    lines: list[str] = [
        f"# Schema: {schema}.{table}",
        "",
        "| Column | Type | Nullable | Key | Default |",
        "|--------|------|----------|-----|---------|",
    ]
    for col_name, data_type, max_len, num_prec, num_scale, nullable, default, key_type in columns_info:
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
        lines.append(f"| {col_name} | {type_str} | {nullable} | {key_str} | {default_str} |")

    return "\n".join(lines)


def _read_dictionary(db: Database) -> str:
    """Return the semantic dictionary file contents, or empty string if not created yet."""
    dict_path = Path(db.dictionary_file)
    if not dict_path.exists():
        return ""
    return dict_path.read_text(encoding="utf-8")
