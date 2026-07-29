# -*- coding: utf-8 -*-
"""
MCP SQL Server - Secure database inspection server
Implements connection pooling, SQL injection prevention, and comprehensive security controls
"""

import asyncio
import logging

import pyodbc
from mcp.server import Server
from mcp.types import Tool, TextContent, CallToolResult, ListToolsResult

from mcp_sqlserver import databases
from mcp_sqlserver.config import _load_config
from mcp_sqlserver import resources
from mcp_sqlserver.tools import (
    handle_list_tables,
    handle_describe_table,
    handle_execute_query,
    handle_table_relationships,
    handle_table_indexes,
    handle_search_columns,
    handle_table_statistics,
    handle_get_views,
    handle_get_procedures,
    handle_explain_query,
    handle_update_dictionary,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
#  Tools                                                              #
# ------------------------------------------------------------------ #

async def list_tools(ctx, params) -> ListToolsResult:
    """List available tools. In multi-db mode every tool gets a required 'database' parameter."""
    tools = [
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
            description="Esegue una query SELECT sul database (limite righe e timeout da configurazione). Solo SELECT permesso.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query SQL SELECT da eseguire",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["markdown", "csv", "json"],
                        "description": "Formato output: markdown (default, valori troncati), csv o json (nessun troncamento, adatti a estrazioni dati)",
                        "default": "markdown",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="explain_query",
            title="Explain Query",
            description="Mostra il piano di esecuzione stimato di una query SELECT senza eseguirla. Utile per diagnosticare query lente e valutare l'uso degli indici.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query SQL SELECT da analizzare (non viene eseguita)",
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
        Tool(
            name="get_procedures",
            title="Get Stored Procedures",
            description="Elenca le stored procedure del database con date di creazione/modifica. Può filtrare per schema o nome (wildcards) e includere la definizione SQL.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema_filter": {
                        "type": "string",
                        "description": "Filtra per schema specifico (opzionale)",
                    },
                    "name_filter": {
                        "type": "string",
                        "description": "Filtra per nome procedura, supporta wildcards (es. sp_ordini*)",
                    },
                    "include_definition": {
                        "type": "boolean",
                        "description": "Includi la definizione SQL (default: false — usare con name_filter per evitare output enormi)",
                        "default": False,
                    },
                },
            },
        ),
        Tool(
            name="update_dictionary",
            title="Update Semantic Dictionary",
            description=(
                "Salva una nuova scoperta semantica nel dizionario del database. "
                "Chiama questo tool ogni volta che scopri un'associazione non ovvia tra linguaggio di business "
                "e schema fisico:\n"
                "- Quando identifichi quale tabella/colonne corrispondono a un'entità nominata dall'utente "
                "(es. 'cliente' → tabella `anagra`)\n"
                "- Quando apprendi un'espressione filtro ricorrente (es. 'attivo' → `stato = 'A'`)\n"
                "- Quando scopri una relazione join non deducibile dai nomi delle colonne\n\n"
                "Non chiamare per informazioni già nel dizionario o per mappings ovvi dal nome della tabella. "
                "Notifica sempre l'utente dopo aver salvato (es. 'Ho salvato nel dizionario che ...').\n\n"
                "Row formats:\n"
                "  entities:  | termine utente | tabella | campi chiave | note |\n"
                "  filters:   | espressione utente | sql equivalente | note |\n"
                "  relations: | tabella da | campo | tabella a | campo | descrizione |"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": ["entities", "filters", "relations"],
                        "description": "Categoria: entities (termini→tabelle), filters (espressioni→SQL), relations (join tra tabelle)",
                    },
                    "key": {
                        "type": "string",
                        "description": "Valore del primo campo della riga (usato per deduplicazione, es. 'cliente')",
                    },
                    "row": {
                        "type": "string",
                        "description": "Riga completa in formato Markdown table, es. '| cliente | anagra | codice, cognome | |'",
                    },
                },
                "required": ["section", "key", "row"],
            },
        ),
    ]

    # In multi-db mode Claude must say which database each call targets
    if databases.is_multi():
        db_property = {
            "type": "string",
            "enum": sorted(databases.DATABASES),
            "description": "Database di destinazione",
        }
        for tool in tools:
            tool.input_schema.setdefault("properties", {})["database"] = db_property
            required = tool.input_schema.setdefault("required", [])
            required.insert(0, "database")

    return ListToolsResult(tools=tools)


_HANDLERS = {
    "list_tables": handle_list_tables,
    "describe_table": handle_describe_table,
    "execute_query": handle_execute_query,
    "get_table_relationships": handle_table_relationships,
    "get_table_indexes": handle_table_indexes,
    "search_columns": handle_search_columns,
    "get_table_statistics": handle_table_statistics,
    "get_views": handle_get_views,
    "get_procedures": handle_get_procedures,
    "explain_query": handle_explain_query,
    "update_dictionary": handle_update_dictionary,
}


async def call_tool(ctx, params) -> CallToolResult:
    """Handle tool calls with proper error handling"""

    name = params.name
    try:
        handler = _HANDLERS.get(name)
        if handler is None:
            logger.error(f"Tool sconosciuto: {name}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Tool '{name}' non riconosciuto")],
                isError=True,
            )

        arguments = dict(params.arguments or {})
        try:
            db = databases.get_database(arguments.pop("database", None))
        except KeyError as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"❌ {e.args[0]}")],
                isError=True,
            )

        # Handlers are synchronous (blocking pyodbc); run in a worker thread so a
        # slow query on one database doesn't block calls to the others
        content = await asyncio.to_thread(handler, db, arguments)
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


# Handlers are passed to the constructor (SDK v2 dropped the decorator API), so the
# server must be built after they are defined.
app = Server(
    "mcp-sqlserver",
    on_list_tools=list_tools,
    on_call_tool=call_tool,
    on_list_resources=resources.list_resources,
    on_list_resource_templates=resources.list_resource_templates,
    on_read_resource=resources.read_resource,
)


async def main():
    """Entry point"""
    _load_config()

    from mcp.server.stdio import stdio_server

    logger.info("Avvio MCP SQL Server...")

    databases.load_databases()
    if not databases.DATABASES:
        logger.error(
            "Nessun database configurato. Usa --databases file.json (multi-db) "
            "o --connection-string / SQL_CONNECTION_STRING (singolo)."
        )
        return

    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
    finally:
        databases.close_all()
        logger.info("MCP SQL Server terminato")


def run():
    """Synchronous entry point for console_scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
