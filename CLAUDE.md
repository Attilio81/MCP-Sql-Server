# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCP SQL Server is a Python MCP (Model Context Protocol) server that exposes SQL Server database inspection and querying capabilities to Claude Desktop and Claude Code. It implements connection pooling, multi-layer SQL injection prevention, schema/table access controls, and the full MCP 2025-11-25 spec (Tools, Resources, Prompts).

## Development Commands

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run unit tests (no database required)
pytest tests/ -v

# Run a single test
pytest tests/test_security_validator.py::test_function_name -v

# Lint
ruff check src/

# Format
ruff format src/

# Test connection to a real SQL Server
python test_connection.py

# Start the server manually (blocks waiting for MCP stdio)
python -m mcp_sqlserver.server --connection-string "Driver={ODBC Driver 17 for SQL Server};Server=...;Database=...;Trusted_Connection=yes"
```

## Architecture

### Module Layout

```
src/mcp_sqlserver/
├── server.py       # MCP app instance, list_tools/call_tool handlers, entry point (run/main)
├── config.py       # CLI arg parsing + env var fallback; module-level globals mutated by _load_config()
├── security.py     # SecurityValidator: is_table_allowed(), validate_query()
├── pool.py         # ConnectionPool: thread-safe Queue-based pool with auto-reconnect
├── helpers.py      # Markdown table formatting
├── resources.py    # MCP Resources: db://schema/overview, db://schema/tables/{name}
├── prompts.py      # MCP Prompts: analyze-table, query-builder, data-dictionary
└── tools/
    ├── __init__.py         # Re-exports all handle_* functions
    ├── list_tables.py
    ├── describe_table.py
    ├── execute_query.py
    ├── relationships.py
    ├── indexes.py
    ├── search_columns.py
    ├── statistics.py
    └── views.py
```

### Key Design Decisions

**Configuration priority**: CLI args → env vars → `.env` file. `_load_config()` is called once at startup from `main()` and mutates module-level globals in `config.py`. All modules import `from mcp_sqlserver import config` and read the globals directly.

**Connection pool**: `ConnectionPool` wraps a `queue.Queue` of `pyodbc` connections. Acquiring uses `pool.get(timeout=...)` (raises `Empty` → converted to `TimeoutError`). Every `get_connection()` context manager pings `SELECT 1` to detect dead connections and replaces them. Connections are always returned to the pool via `finally`, with a rollback and replacement-on-failure.

**Security validation**: `SecurityValidator` in `security.py` has two public class methods:
- `is_table_allowed(table_name, schema)` — validates identifier format, schema whitelist, and blacklist wildcard patterns.
- `validate_query(query)` — six ordered layers: length cap (4096 chars), null-byte check, Unicode normalisation, SELECT-only enforcement, injection regex patterns, dangerous keyword word-boundary check.

**Tool handler pattern**: Each tool lives in its own file under `tools/` and exports a single `async def handle_*(pool, arguments)` function returning `list[TextContent]`. `server.py` dispatches via a plain `if/elif` chain in `call_tool()`. To add a new tool: create the handler file, re-export from `tools/__init__.py`, add a `Tool(...)` entry in `list_tools()`, and add the dispatch branch in `call_tool()`.

**MCP resources and prompts** are registered at module load time via `register_resources(app, get_pool)` and `register_prompts(app)` called at the top of `server.py`, before the tool decorators.

### Adding a New Tool

1. Create `src/mcp_sqlserver/tools/my_tool.py` with `async def handle_my_tool(pool, arguments)`.
2. Re-export from `tools/__init__.py`.
3. Add `Tool(name="my_tool", ...)` to `list_tools()` in `server.py`.
4. Add `elif name == "my_tool": content = await handle_my_tool(pool, arguments)` in `call_tool()`.
5. Add tests in `tests/`.
6. Update README.md under "Available Tools".

## Testing Notes

The unit test suite (`tests/test_security_validator.py`) covers `SecurityValidator` and `helpers` without a real database. All new security logic must have unit tests. Integration testing requires a real SQL Server and ODBC Driver 17+.
