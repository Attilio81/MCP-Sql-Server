# MCP SQL Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-2025--11--25-green.svg)](https://modelcontextprotocol.io/specification/2025-11-25)
[![Tests](https://img.shields.io/badge/tests-128%20passing-brightgreen.svg)](tests/)

A secure, production-ready [Model Context Protocol](https://modelcontextprotocol.io/) server that lets Claude Desktop and Claude Code inspect and query SQL Server databases — read-only by design, with multi-layer SQL injection prevention, table/schema access controls, and a self-learning semantic dictionary.

```
You:    How many orders did Mario Rossi place this year?
Claude: (explores schema → finds anagra + ordini → runs a validated SELECT)
        Mario Rossi placed 47 orders in 2026, totalling €12,350.
        I saved to the dictionary that "customer by name" maps to anagra.cognome + nome.
```

## Highlights

- **Read-only by design** — only `SELECT` statements pass validation; six ordered defence layers block everything else
- **Access control** — table blacklist with wildcards (`sys_*`, `*_audit`) and schema whitelist, enforced on *every* tool including free-form queries
- **11 inspection tools** — tables, schemas, indexes, foreign keys, statistics, views, stored procedures, execution plans, column search
- **Flexible output** — query results as Markdown, CSV, or JSON
- **Semantic dictionary** — Claude auto-accumulates business-term → schema mappings per database and reloads them each session
- **Connection pooling** — thread-safe pool with dead-connection detection and automatic reconnect
- **Web manager UI** — add, edit, test, and register database connections without touching JSON

## Table of Contents

- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Tools](#tools)
- [Resources](#resources)
- [Semantic Dictionary](#semantic-dictionary)
- [SQL MCP Manager](#sql-mcp-manager)
- [Security](#security)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## Quick Start

### Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | |
| SQL Server | Any recent version, on-prem or Azure SQL |
| ODBC Driver 17+ | [Download from Microsoft](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) |
| Claude Desktop or Claude Code | |

### Install

```bash
git clone https://github.com/Attilio81/MCP-Sql-Server.git
cd MCP-Sql-Server
```

**Windows:** run `setup.bat` &nbsp;·&nbsp; **Linux/macOS:** run `./setup.sh`

Or manually:

```bash
pip install -e .
python test_connection.py   # verifies driver, connection, and MCP install
```

<details>
<summary><b>ODBC driver installation (Linux / macOS)</b></summary>

**Ubuntu/Debian:**
```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17
```

**macOS:**
```bash
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
brew update && brew install msodbcsql17
```
</details>

## Configuration

One server process serves **all your databases**. Databases are defined in a JSON file passed via `--databases`; every tool then takes a `database` parameter (with autocomplete of the configured names). The [Manager UI](#sql-mcp-manager) maintains this file for you — including automatic migration of old per-database config entries.

### Multi-database mode (recommended)

`~/.mcp_sqlserver/databases.json` — one block per database, each with its own limits and security rules:

```json
{
  "sales": {
    "connection_string": "Driver={ODBC Driver 17 for SQL Server};Server=srv1;Database=Sales;Trusted_Connection=yes",
    "max_rows": 100,
    "allowed_schemas": "dbo",
    "blacklist_tables": "sys_*,*_audit"
  },
  "warehouse": {
    "connection_string": "Driver={ODBC Driver 17 for SQL Server};Server=srv2;Database=WH;UID=user;PWD=password"
  }
}
```

**Claude Desktop** — single entry in `claude_desktop_config.json` (`%APPDATA%\Claude\` on Windows, `~/Library/Application Support/Claude/` on macOS, `~/.config/Claude/` on Linux):

```json
{
  "mcpServers": {
    "sqlserver": {
      "command": "python",
      "args": ["-m", "mcp_sqlserver.server", "--databases", "C:\\Users\\you\\.mcp_sqlserver\\databases.json"]
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add sqlserver --scope user -- python -m mcp_sqlserver.server \
  --databases "C:\Users\you\.mcp_sqlserver\databases.json"
```

Connection pools are created lazily — only databases actually used in a session open connections.

> *"On the **warehouse** database, show me the Stock table"* — Claude passes `database: "warehouse"` on each tool call.

### Single-database mode (legacy)

Still fully supported — pass `--connection-string` instead of `--databases`; the `database` tool parameter becomes optional:

```json
"args": [
  "-m", "mcp_sqlserver.server",
  "--connection-string", "Driver={ODBC Driver 17 for SQL Server};Server=SRV;Database=DB;Trusted_Connection=yes",
  "--allowed-schemas", "dbo"
]
```

> Claude Desktop and Claude Code use **separate configuration stores**. The Manager UI keeps the Desktop config in sync automatically and registers the server on Claude Code with one click. Details in [CLAUDE_CODE_USAGE.md](CLAUDE_CODE_USAGE.md).

### Parameters

Per-database keys in `databases.json`: `connection_string` (required), `max_rows`, `query_timeout`, `pool_size`, `pool_timeout`, `allowed_schemas`, `blacklist_tables`, `dictionary_file` (default: `<name>_dictionary.md` next to databases.json). Lists accept both JSON arrays and comma-separated strings.

CLI arguments (single-db mode / global):

| CLI argument | Env variable | Default | Description |
|---|---|---|---|
| `--databases` | `DATABASES_FILE` | *(none)* | Path to databases.json — enables multi-database mode |
| `--connection-string` | `SQL_CONNECTION_STRING` | *(required in single-db mode)* | ODBC connection string |
| `--max-rows` | `MAX_ROWS` | `100` | Max rows per query (a `TOP` clause is injected if missing) |
| `--query-timeout` | `QUERY_TIMEOUT` | `30` | Query timeout, seconds |
| `--pool-size` | `POOL_SIZE` | `5` | Connection pool size |
| `--pool-timeout` | `POOL_TIMEOUT` | `30` | Pool acquisition timeout, seconds |
| `--blacklist-tables` | `BLACKLIST_TABLES` | *(none)* | Comma-separated deny patterns, wildcards supported |
| `--allowed-schemas` | `ALLOWED_SCHEMAS` | *(all)* | Comma-separated schema whitelist |
| `--dictionary-file` | `DICTIONARY_FILE` | `semantic_dictionary.md` | Semantic dictionary path (absolute recommended) |
| `--log-level` | `LOG_LEVEL` | `INFO` | `DEBUG` · `INFO` · `WARNING` · `ERROR` · `CRITICAL` |

**Connection string variants:**

```text
# Windows integrated authentication
Driver={ODBC Driver 17 for SQL Server};Server=SRV;Database=DB;Trusted_Connection=yes

# SQL authentication
Driver={ODBC Driver 17 for SQL Server};Server=SRV;Database=DB;UID=user;PWD=password

# Azure SQL with Entra ID
Driver={ODBC Driver 17 for SQL Server};Server=srv.database.windows.net;Database=DB;Authentication=ActiveDirectoryInteractive
```

## Tools

| Tool | Purpose | Key parameters |
|---|---|---|
| `list_tables` | All accessible tables with row counts | `schema_filter` |
| `describe_table` | Columns, types, constraints + sample rows | `table_name`, `sample_rows` (≤50) |
| `execute_query` | Validated `SELECT` with row cap and timeout | `query`, `format` (`markdown`/`csv`/`json`) |
| `explain_query` | Estimated execution plan — query is **not** executed | `query` |
| `get_table_relationships` | Foreign keys to and from a table | `table_name` |
| `get_table_indexes` | Indexes: type, columns, uniqueness, fill factor | `table_name` |
| `search_columns` | Find columns by name across the database | `column_pattern` (wildcards), `schema_filter` |
| `get_table_statistics` | Per-column stats: distinct, NULLs, min/max | `table_name` |
| `get_views` | Views with optional SQL definition | `schema_filter`, `include_definition` |
| `get_procedures` | Stored procedures with optional SQL definition | `schema_filter`, `name_filter`, `include_definition` |
| `update_dictionary` | Persist a semantic discovery (called by Claude) | `section`, `key`, `row` |

Notes:

- In multi-database mode every tool takes a required `database` parameter (enum of configured names) selecting which database the call targets.
- `execute_query` injects `TOP {max_rows}` when missing and runs under `READ COMMITTED` isolation. `format: csv` / `json` return untruncated values — use them for real data extraction; the default Markdown table truncates long values for readability.
- `explain_query` uses `SET SHOWPLAN_ALL`: SQL Server returns the optimizer's plan (operations, estimated rows, subtree cost) without touching data. Useful to diagnose slow queries and verify index usage.
- `get_procedures` defaults to `include_definition: false`; combine with `name_filter` (e.g. `sp_orders*`) to fetch specific definitions without flooding the context.
- Every tool enforces the blacklist and schema whitelist — including tables referenced inside free-form queries via `FROM`, `JOIN`, `APPLY`, comma-joins, and subqueries.

### Example Session

> **You:** *Show me all the tables* — Claude calls `list_tables`
>
> **You:** *Why is this report slow?* — Claude calls `explain_query`, spots a table scan, suggests an index
>
> **You:** *Export all 2026 orders as CSV* — Claude calls `execute_query` with `format: "csv"`
>
> **You:** *Run: `SELECT * FROM users; DROP TABLE Orders--`*
>
> **Claude:** 🔒 Query not valid: **stacked statements (semicolons) are not allowed**

## Resources

MCP Resources provide read-only context that clients load automatically:

| URI | Content |
|---|---|
| `db://{name}/schema/overview` | Full schema: all tables, columns, types, primary keys |
| `db://{name}/schema/tables/{table}` | Detailed schema for one table |
| `db://{name}/dictionary` | Semantic dictionary, auto-loaded at session start |

In single-database mode the unnamed legacy URIs (`db://schema/overview`, `db://dictionary`, ...) keep working.

## Semantic Dictionary

Every business database has a vocabulary the schema alone can't reveal: `anagra` means nothing, *customers* does. The semantic dictionary is a per-database Markdown file where Claude accumulates this knowledge as you work — no manual documentation required.

**The loop:**

1. You ask a business question ("how many sales did Mario Rossi make?")
2. Claude explores the schema and finds the answer
3. Claude saves the non-obvious mapping via `update_dictionary` and tells you it did
4. Next session, `db://{name}/dictionary` is loaded automatically — Claude starts already informed

The file has three sections — business entities (term → table), filter aliases ("active" → `stato = 'A'`), and notable join relationships. It is plain Markdown: edit it by hand or through the Manager's 📖 editor whenever you want.

Each database gets its own dictionary automatically (`<name>_dictionary.md` next to `databases.json`) — different domains, different vocabularies. Override per database with the `dictionary_file` key.

> Full guide: [`docs/manuale-dizionario-semantico.md`](docs/manuale-dizionario-semantico.md)

## SQL MCP Manager

A local web UI to manage all your SQL Server MCP connections from one page.

```bat
start-manager.bat        # Windows — or: python -m manager.server
```

Then open <http://localhost:8090>. Requires `pip install -e ".[manager]"` (done by `setup.bat`).

- **Add / edit / delete** databases in `databases.json`; the single `sqlserver` entry in `claude_desktop_config.json` is kept in sync automatically (other entries untouched)
- **Auto-migrates** old per-database config entries into `databases.json` on first load
- **Test** any connection before saving; on page load every database is probed in parallel (status rail per card)
- **Duplicate** a database to onboard a new client on the same ERP layout, **copy** its connection string, **filter** the list by name/server/database
- **"Registra su Claude Code"** registers the multi-database server on Claude Code (`claude mcp add --scope user`) with one click
- **📖 button** opens the semantic dictionary editor for that database
- **Auto-detects** the Claude Desktop config path on Windows, macOS, and Linux

## Security

Defence in depth, applied in order on every query:

1. **Length cap** (4096 chars) — payload DoS prevention
2. **Null-byte rejection**
3. **Unicode normalisation** — full-width lookalikes folded before matching
4. **SELECT-only enforcement**
5. **Injection patterns** — semicolons, comments, `UNION`, `EXEC()`, hex/`CHAR()` encoding, timing attacks
6. **Dangerous keywords** — word-boundary match on DML/DDL/admin commands (`INSERT`…`SHUTDOWN`, `xp_*`)

Plus table-level enforcement on every tool: identifier format validation, schema whitelist, blacklist wildcards — including tables referenced inside free-form `SELECT`s (`FROM`/`JOIN`/`APPLY`/subqueries).

**Recommended setup:**

- Connect with a **dedicated read-only SQL login** (validation is a second line of defence, not a substitute for DB permissions)
- Prefer **Windows integrated auth** or Entra ID over passwords in config files
- Whitelist only the schemas Claude needs (`--allowed-schemas dbo`)
- Blacklist sensitive tables (`--blacklist-tables *_audit,password*`)

Details and threat model: [SECURITY.md](SECURITY.md)

## Development

```
src/mcp_sqlserver/       # the MCP server
├── server.py            # MCP app, tool registration and dispatch, entry point
├── config.py            # CLI args + env vars
├── security.py          # SecurityValidator: query validation, table extraction, access rules
├── pool.py              # thread-safe connection pool with auto-reconnect
├── helpers.py           # Markdown / CSV / JSON result formatting
├── resources.py         # MCP Resources
└── tools/               # one module per tool handler
manager/                 # FastAPI web UI (config manager + connection tester)
tests/                   # unit tests, no database required
```

```bash
pip install -e ".[dev,manager]"
pytest tests/ -v          # 128 unit tests, no DB needed
ruff check src/
```

All security logic is covered by unit tests (`tests/test_security_validator.py`). Integration testing requires a real SQL Server — use `python test_connection.py`.

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Troubleshooting

<details>
<summary><b>"Data source name not found"</b></summary>

The ODBC driver is missing or the name in the connection string doesn't match. List installed drivers:
```bash
python -c "import pyodbc; print(pyodbc.drivers())"
```
</details>

<details>
<summary><b>"Timeout acquiring connection from pool"</b></summary>

Increase `--pool-size` / `--pool-timeout`, or check for long-running queries holding connections.
</details>

<details>
<summary><b>"Schema 'xyz' is not authorised"</b></summary>

Add the schema to `--allowed-schemas`, or remove the argument to allow all schemas.
</details>

<details>
<summary><b>Server not appearing in Claude</b></summary>

Restart Claude Desktop after config changes. For Claude Code run `claude mcp list` to verify registration. Enable `--log-level DEBUG` and check logs (Claude Desktop: **Help → Show Logs**).
</details>

## Roadmap

- [x] CSV / JSON export
- [x] Execution plan analysis
- [x] Stored procedure inspection
- [x] Single-server multi-database mode (one process, many databases)
- [ ] Query audit log
- [ ] PostgreSQL / MySQL support

## License

MIT — see [LICENSE](LICENSE).

Built with the [Model Context Protocol](https://modelcontextprotocol.io/) and [pyodbc](https://github.com/mkleehammer/pyodbc).
