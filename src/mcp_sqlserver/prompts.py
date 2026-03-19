# -*- coding: utf-8 -*-
"""
MCP Prompt templates for SQL Server database workflows.
"""

from mcp.types import (
    TextContent,
    Prompt, PromptArgument, PromptMessage, GetPromptResult,
)


def register_prompts(app):
    """Register all prompt handlers on the MCP app."""

    @app.list_prompts()
    async def list_prompts() -> list[Prompt]:
        """List available prompt templates."""
        return [
            Prompt(
                name="analyze-table",
                title="Analyze Table",
                description="Analizza la struttura di una tabella e suggerisce osservazioni su schema, tipi e relazioni",
                arguments=[
                    PromptArgument(
                        name="table_name",
                        description="Nome della tabella (formato: schema.table o solo table per dbo)",
                        required=True,
                    ),
                ],
            ),
            Prompt(
                name="query-builder",
                title="Query Builder",
                description="Aiuta a costruire una query SELECT a partire da una descrizione in linguaggio naturale",
                arguments=[
                    PromptArgument(
                        name="description",
                        description="Descrizione in linguaggio naturale di cosa cercare (es. 'ordini del 2026 raggruppati per mese')",
                        required=True,
                    ),
                    PromptArgument(
                        name="tables",
                        description="Tabelle coinvolte, separate da virgola (es. 'Orders,Customers')",
                        required=False,
                    ),
                ],
            ),
            Prompt(
                name="data-dictionary",
                title="Data Dictionary",
                description="Genera un data dictionary completo per una o più tabelle del database",
                arguments=[
                    PromptArgument(
                        name="tables",
                        description="Tabelle da documentare, separate da virgola (vuoto = tutte le tabelle accessibili)",
                        required=False,
                    ),
                ],
            ),
        ]

    @app.get_prompt()
    async def get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
        """Return a prompt by name with filled arguments."""
        arguments = arguments or {}

        if name == "analyze-table":
            table_name = arguments.get("table_name", "")
            if not table_name:
                raise ValueError("Argomento 'table_name' richiesto")
            return GetPromptResult(
                description=f"Analisi della tabella {table_name}",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=(
                                f"Analizza la tabella '{table_name}' nel database SQL Server.\n\n"
                                "Per favore:\n"
                                "1. Usa il tool 'describe_table' per ottenere lo schema completo\n"
                                "2. Usa il tool 'get_table_relationships' per vedere le relazioni\n"
                                "3. Usa il tool 'execute_query' per un conteggio righe e statistiche base\n\n"
                                "Poi fornisci:\n"
                                "- Panoramica della struttura della tabella\n"
                                "- Osservazioni sui tipi di dato scelti\n"
                                "- Analisi delle relazioni con altre tabelle\n"
                                "- Eventuali suggerimenti per miglioramenti allo schema"
                            ),
                        ),
                    ),
                ],
            )

        elif name == "query-builder":
            description = arguments.get("description", "")
            if not description:
                raise ValueError("Argomento 'description' richiesto")
            tables = arguments.get("tables", "")
            tables_hint = f"\nTabelle da usare: {tables}" if tables else ""
            return GetPromptResult(
                description=f"Costruzione query: {description}",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=(
                                f"Ho bisogno di una query SQL Server per: {description}\n"
                                f"{tables_hint}\n\n"
                                "Per favore:\n"
                                "1. Usa 'list_tables' per vedere le tabelle disponibili\n"
                                "2. Usa 'describe_table' per capire la struttura delle tabelle rilevanti\n"
                                "3. Costruisci una query SELECT ottimizzata\n"
                                "4. Eseguila con 'execute_query' e mostra i risultati\n\n"
                                "Ricorda: solo query SELECT sono permesse. "
                                "Usa JOIN dove necessario e alias chiari per le colonne."
                            ),
                        ),
                    ),
                ],
            )

        elif name == "data-dictionary":
            tables = arguments.get("tables", "")
            if tables:
                scope = f"le tabelle: {tables}"
            else:
                scope = "tutte le tabelle accessibili"
            return GetPromptResult(
                description=f"Data dictionary per {scope}",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=(
                                f"Genera un data dictionary completo per {scope} nel database.\n\n"
                                "Per favore:\n"
                                "1. Usa 'list_tables' per elencare le tabelle\n"
                                "2. Per ogni tabella, usa 'describe_table' per ottenere lo schema\n"
                                "3. Usa 'get_table_relationships' per le relazioni\n\n"
                                "Per ogni tabella, documenta:\n"
                                "- Nome e scopo presunto della tabella\n"
                                "- Elenco colonne con tipo, nullable, chiave e descrizione stimata\n"
                                "- Relazioni (FK in entrata e in uscita)\n"
                                "- Conteggio righe approssimativo\n\n"
                                "Formatta il risultato in Markdown strutturato, pronto per la documentazione."
                            ),
                        ),
                    ),
                ],
            )

        raise ValueError(f"Prompt sconosciuto: {name}")
