# -*- coding: utf-8 -*-
"""
MCP SQL Server - Secure database inspection server
Implements connection pooling, SQL injection prevention, and comprehensive security controls
"""

import asyncio
import logging
from typing import Any, Optional

import pyodbc
from mcp.server import Server
from mcp.types import Tool, TextContent, CallToolResult

from mcp_sqlserver import config
from mcp_sqlserver.config import _load_config
from mcp_sqlserver.pool import ConnectionPool
from mcp_sqlserver.security import SecurityValidator
from mcp_sqlserver.helpers import format_table_data
from mcp_sqlserver.resources import register_resources
from mcp_sqlserver.tools import (
    handle_list_tables,
    handle_describe_table,
    handle_execute_query,
    handle_table_relationships,
    handle_table_indexes,
    handle_search_columns,
    handle_table_statistics,
    handle_get_views,
)

logger = logging.getLogger(__name__)

# Initialize MCP server
app = Server("mcp-sqlserver")

# Initialize connection pool (will be created on first use)
connection_pool: Optional[ConnectionPool] = None


def get_pool() -> ConnectionPool:
    """Get or create connection pool"""
    global connection_pool
    if connection_pool is None:
        connection_pool = ConnectionPool(config.CONNECTION_STRING, config.POOL_SIZE, config.POOL_TIMEOUT)
    return connection_pool


# ------------------------------------------------------------------ #
#  Register Resources & Prompts                                       #
# ------------------------------------------------------------------ #

register_resources(app, get_pool)


# ------------------------------------------------------------------ #
#  Tools                                                              #
# ------------------------------------------------------------------ #

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="list_tables",
            title="List Tables",
            description="Elenca tutte le tabelle accessibili del database con conteggio righe e informazioni schema",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema_filter": {
                        "type": "string",
                        "description": "Filtra per schema specifico (opzionale)",
                    }
                },
            },
        ),
        Tool(
            name="describe_table",
            title="Describe Table",
            description="Mostra schema completo di una tabella (colonne, tipi, constraints) con opzionali righe di esempio",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Nome della tabella (formato: schema.table o solo table per dbo)",
                    },
                    "sample_rows": {
                        "type": "integer",
                        "description": "Numero di righe di esempio (default: 10, max: 50)",
                        "default": 10,
                        "minimum": 0,
                        "maximum": 50,
                    },
                },
                "required": ["table_name"],
            },
        ),
        Tool(
            name="execute_query",
            title="Execute Query",
            description=f"Esegue una query SELECT sul database (max {config.MAX_ROWS} righe, timeout {config.QUERY_TIMEOUT}s). Solo SELECT permesso.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query SQL SELECT da eseguire",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_table_relationships",
            title="Get Table Relationships",
            description="Mostra le relazioni (foreign keys) di una tabella con altre tabelle",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Nome della tabella (formato: schema.table o solo table per dbo)",
                    },
                },
                "required": ["table_name"],
            },
        ),
        Tool(
            name="get_table_indexes",
            title="Get Table Indexes",
            description="Mostra gli indici di una tabella: nome, tipo (clustered/nonclustered), colonne, unicità e fill factor",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Nome della tabella (formato: schema.table o solo table per dbo)",
                    },
                },
                "required": ["table_name"],
            },
        ),
        Tool(
            name="search_columns",
            title="Search Columns",
            description="Cerca colonne per nome in tutto il database con supporto wildcards (es. *email*, user_id). Utile per trovare dove risiede un certo dato.",
            inputSchema={
                "type": "object",
                "properties": {
                    "column_pattern": {
                        "type": "string",
                        "description": "Pattern di ricerca per nome colonna (supporta wildcards: *email*, user_*)",
                    },
                    "schema_filter": {
                        "type": "string",
                        "description": "Filtra per schema specifico (opzionale)",
                    },
                },
                "required": ["column_pattern"],
            },
        ),
        Tool(
            name="get_table_statistics",
            title="Get Table Statistics",
            description="Mostra statistiche aggregate per ogni colonna di una tabella: conteggio righe, valori distinti, NULL count, min/max per colonne numeriche e date",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Nome della tabella (formato: schema.table o solo table per dbo)",
                    },
                },
                "required": ["table_name"],
            },
        ),
        Tool(
            name="get_views",
            title="Get Views",
            description="Elenca le viste del database con definizione SQL opzionale. Può filtrare per schema e mostrare o nascondere il DDL.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema_filter": {
                        "type": "string",
                        "description": "Filtra per schema specifico (opzionale)",
                    },
                    "include_definition": {
                        "type": "boolean",
                        "description": "Includi la definizione SQL della vista (default: true)",
                        "default": True,
                    },
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> CallToolResult:
    """Handle tool calls with proper error handling"""

    try:
        pool = get_pool()

        if name == "list_tables":
            content = await handle_list_tables(pool, arguments)
        elif name == "describe_table":
            content = await handle_describe_table(pool, arguments)
        elif name == "execute_query":
            content = await handle_execute_query(pool, arguments)
        elif name == "get_table_relationships":
            content = await handle_table_relationships(pool, arguments)
        elif name == "get_table_indexes":
            content = await handle_table_indexes(pool, arguments)
        elif name == "search_columns":
            content = await handle_search_columns(pool, arguments)
        elif name == "get_table_statistics":
            content = await handle_table_statistics(pool, arguments)
        elif name == "get_views":
            content = await handle_get_views(pool, arguments)
        else:
            logger.error(f"Tool sconosciuto: {name}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Tool '{name}' non riconosciuto")],
                isError=True,
            )

        return CallToolResult(content=content, isError=False)

    except TimeoutError as e:
        logger.error(f"Timeout: {e}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"⏱️ Timeout: {str(e)}")],
            isError=True,
        )
    except pyodbc.Error as e:
        logger.error(f"Errore database: {e}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ Errore database: {str(e)}")],
            isError=True,
        )
    except Exception as e:
        logger.exception(f"Errore inaspettato in {name}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"❌ Errore: {str(e)}")],
            isError=True,
        )


async def main():
    """Entry point"""
    _load_config()

    from mcp.server.stdio import stdio_server

    logger.info("Avvio MCP SQL Server...")

    if not config.CONNECTION_STRING:
        logger.error("SQL_CONNECTION_STRING non configurata. Imposta la variabile d'ambiente o usa --connection-string.")
        return

    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
    finally:
        # Cleanup connection pool
        if connection_pool:
            connection_pool.close_all()
        logger.info("MCP SQL Server terminato")


def run():
    """Synchronous entry point for console_scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
