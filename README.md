# MCP SQL Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-2025--11--25-green.svg)](https://modelcontextprotocol.io/specification/2025-11-25)

A secure and production-ready MCP (Model Context Protocol) server for SQL Server database inspection and querying, designed for seamless integration with Claude Desktop and Claude Code.

## Features

- **Connection Pooling**: Efficient connection management with configurable pool size
- **Advanced Security**:
  - SQL injection prevention with prepared statements
  - Table blacklist with wildcard support (`sys_*`, `*_audit`, etc.)
  - Schema whitelist for access control
  - Query validation (SELECT-only with dangerous keyword detection)
  - Identifier validation to prevent injection
- **Robust Error Handling**: Detailed logging with configurable levels
- **Complete MCP Tools**:
  - `list_tables`: List all accessible tables with metrics (row count, size)
  - `describe_table`: Show complete schema with sample data
  - `execute_query`: Execute safe SELECT queries with timeout
  - `get_table_relationships`: Analyze foreign key relationships
  - `get_table_indexes`: Show indexes with type, columns, uniqueness and fill factor
  - `search_columns`: Search columns by name across all tables (wildcard support)
  - `get_table_statistics`: Per-column statistics (distinct values, NULLs, min/max)
  - `get_views`: List database views with optional SQL definitions
- **MCP Resources**:
  - `db://schema/overview`: Full database schema overview (all tables, columns, types, PKs)
  - `db://schema/tables/{table_name}`: Detailed schema for a single table
- **MCP Prompts**:
  - `analyze-table`: Guided analysis of a table's structure, types and relationships
  - `query-builder`: Build a SELECT query from a natural language description
  - `data-dictionary`: Generate a complete data dictionary for one or more tables

## SQL MCP Manager

A built-in web UI for managing SQL Server MCP connections — add, edit, delete, and test all your configured databases from a single page, without editing JSON manually.

### Install & Run

```bash
# Install manager dependencies (FastAPI + uvicorn)
pip install -e ".[manager]"

# Start the manager — opens browser automatically
python -m manager.server
# → http://localhost:8090
```

### What It Does

- **Add / Edit / Delete** SQL Server connections stored in `claude_desktop_config.json`
- **Test** any connection string before saving — shows ✅ or ❌ with the error message
- **Live status** — on page load, all configured servers are tested in parallel and shown as green/red dots
- **Register on Claude Code** — one click on the **CC** button runs `claude mcp add` to make the server available in Claude Code too
- **Preserves** all other entries in your Claude Desktop config untouched
- **Auto-detects** the config file path on Windows, macOS, and Linux

### Interface

Each configured connection appears as a card:

```
● db-vendite         🖥 srv1 › Vendite    schema: dbo    max 100 righe    timeout 30s    [⚡] [✏️] [🗑]
● db-magazzino       🖥 srv2 › Magazzino  schema: dbo,wms max 200 righe   timeout 60s    [⚡] [✏️] [🗑]
✗ db-contabilita     🖥 srv1 › Contabilita                                ✗ Connessione fallita  [⚡] [✏️] [🗑]
```

The form (add/edit) includes: Name, Connection String, Max Rows, Allowed Schemas, Blacklist Tables, Query Timeout, Pool Size, Pool Timeout.

Card actions: **⚡** test connection · **CC** register on Claude Code · **✏️** edit · **🗑** delete

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- SQL Server (any version)
- ODBC Driver 17+ for SQL Server
- Claude Desktop or Claude Code

### Installation

**Option 1: Automated Setup (Recommended)**

**Windows:**
```bash
git clone https://github.com/Attilio81/MCP-Sql-Server.git
cd MCP-Sql-Server
setup.bat
```

**Linux/macOS:**
```bash
git clone https://github.com/Attilio81/MCP-Sql-Server.git
cd MCP-Sql-Server
chmod +x setup.sh
./setup.sh
```

**Option 2: Manual Setup**

```bash
# Clone repository
git clone https://github.com/Attilio81/MCP-Sql-Server.git
cd MCP-Sql-Server

# Install package
pip install -e .

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Test connection
python test_connection.py
```

### ODBC Driver Installation

<details>
<summary><b>Windows</b></summary>

Download from [Microsoft](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)

Or via Chocolatey:
```powershell
choco install sqlserver-odbcdriver
```
</details>

<details>
<summary><b>Linux (Ubuntu/Debian)</b></summary>

```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17
```
</details>

<details>
<summary><b>macOS</b></summary>

```bash
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
brew update
brew install msodbcsql17
```
</details>

## Configuration

All parameters are passed as **command-line arguments** directly in the Claude config file — no `.env` file required. CLI arguments take precedence over environment variables and `.env`.

### Claude Desktop Configuration

Edit `claude_desktop_config.json`:

| Platform | Path |
|---|---|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

```json
{
  "mcpServers": {
    "sqlserver": {
      "command": "python",
      "args": [
        "-m", "mcp_sqlserver.server",
        "--connection-string", "Driver={ODBC Driver 17 for SQL Server};Server=YOUR_SERVER;Database=YOUR_DB;UID=user;PWD=password",
        "--max-rows", "100",
        "--query-timeout", "30",
        "--pool-size", "5",
        "--pool-timeout", "30",
        "--blacklist-tables", "sys_*,*_audit,*_temp",
        "--allowed-schemas", "dbo",
        "--log-level", "INFO"
      ]
    }
  }
}
```

Restart Claude Desktop after editing.

#### Windows Trusted Authentication (no password)

```json
"--connection-string", "Driver={ODBC Driver 17 for SQL Server};Server=YOUR_SERVER;Database=YOUR_DB;Trusted_Connection=yes"
```

#### Azure SQL

```json
"--connection-string", "Driver={ODBC Driver 17 for SQL Server};Server=YOUR_SERVER.database.windows.net;Database=YOUR_DB;Authentication=ActiveDirectoryInteractive"
```

### Multiple Databases

Define one MCP server entry per database — Claude will have all of them available simultaneously and will route queries to the right one based on the server name or your instructions:

```json
{
  "mcpServers": {
    "db-vendite": {
      "command": "python",
      "args": [
        "-m", "mcp_sqlserver.server",
        "--connection-string", "Driver={ODBC Driver 17 for SQL Server};Server=srv1;Database=Vendite;Trusted_Connection=yes",
        "--allowed-schemas", "dbo",
        "--max-rows", "100"
      ]
    },
    "db-magazzino": {
      "command": "python",
      "args": [
        "-m", "mcp_sqlserver.server",
        "--connection-string", "Driver={ODBC Driver 17 for SQL Server};Server=srv2;Database=Magazzino;UID=user;PWD=password",
        "--allowed-schemas", "dbo,wms"
      ]
    },
    "db-contabilita": {
      "command": "python",
      "args": [
        "-m", "mcp_sqlserver.server",
        "--connection-string", "Driver={ODBC Driver 17 for SQL Server};Server=srv1;Database=Contabilita;Trusted_Connection=yes",
        "--blacklist-tables", "*_audit,sys_*"
      ]
    }
  }
}
```

In the chat you can then ask:
> *"On the **Magazzino** database, show me all tables"*
> *"On the **Vendite** database, how many orders were placed in 2026?"*

### Claude Code Configuration

Create `.claude/mcp.json` in your project directory (already in `.gitignore`):

```json
{
  "mcpServers": {
    "sqlserver": {
      "command": "python",
      "args": [
        "-m", "mcp_sqlserver.server",
        "--connection-string", "Driver={ODBC Driver 17 for SQL Server};Server=YOUR_SERVER;Database=YOUR_DB;Trusted_Connection=yes"
      ]
    }
  }
}
```

See [CLAUDE_CODE_USAGE.md](CLAUDE_CODE_USAGE.md) for detailed Claude Code integration.

### All Available Parameters

| CLI Argument | Env Variable | Default | Description |
|---|---|---|---|
| `--connection-string` | `SQL_CONNECTION_STRING` | *(required)* | ODBC connection string |
| `--max-rows` | `MAX_ROWS` | `100` | Max rows returned per query |
| `--query-timeout` | `QUERY_TIMEOUT` | `30` | Query timeout in seconds |
| `--pool-size` | `POOL_SIZE` | `5` | Connection pool size |
| `--pool-timeout` | `POOL_TIMEOUT` | `30` | Pool acquisition timeout (s) |
| `--blacklist-tables` | `BLACKLIST_TABLES` | *(none)* | Comma-separated patterns, wildcards ok |
| `--allowed-schemas` | `ALLOWED_SCHEMAS` | *(all)* | Comma-separated schema whitelist |
| `--log-level` | `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |

## Usage

You **never need to pass credentials or connection strings in the chat**. The connection is configured once in the config file and is transparent in every conversation.

### Example Chat Session

**You:** *Show me all the tables in the database*

**Claude:** *(calls `list_tables`)* 
```
# Database Tables — 12 found

## Schema: dbo
- **Customers** (15,432 rows, 2.14 MB)
- **Orders** (98,201 rows, 8.77 MB)
- **Products** (1,203 rows, 0.43 MB)
- ~~audit_trail~~ 🔒 matches blacklist pattern *_trail
```

---

**You:** *Describe the Orders table with 5 sample rows*

**Claude:** *(calls `describe_table`)* 
```
# Schema: dbo.Orders

| Column      | Type          | Nullable | Key |
|-------------|---------------|----------|-----|
| OrderID     | int(10)       | NO       | PK  |
| CustomerID  | int(10)       | NO       |     |
| OrderDate   | datetime      | NO       |     |
| TotalAmount | decimal(18,2) | YES      |     |
```

---

**You:** *How many orders per month in 2026?*

**Claude:** *(calls `execute_query`)* 
```sql
SELECT TOP 100 MONTH(OrderDate) AS Month, COUNT(*) AS Orders
FROM dbo.Orders
WHERE YEAR(OrderDate) = 2026
GROUP BY MONTH(OrderDate)
ORDER BY Month
```
| Month | Orders |
|-------|--------|
| 1     | 1,203  |
| 2     | 987    |
| 3     | 1,456  |

---

**You:** *Run: SELECT * FROM users; DROP TABLE Orders--*

**Claude:** 🔒 Query not valid: **Stacked statements (semicolons) are not allowed**

---

### With Multiple Databases

When multiple servers are configured, address them by name:

- *"On the **db-vendite** database, show me all tables"*
- *"On **db-magazzino**, describe the Stock table"*
- *"Compare orders between **db-vendite** and **db-contabilita**"*

### With Claude Code

```bash
# Start Claude Code in your project directory
cd your-project
claude

# Then ask naturally:
"List all tables in the database"
"Analyze the Users table and generate a SQLAlchemy model"
"Find all orders from 2026 and summarize them by customer"
```

### Available Tools

#### `list_tables`

Lists all accessible tables with metrics.

**Parameters:**
- `schema_filter` (optional): Filter by specific schema

**Example:**
```
List all tables in the sales schema
```

#### `describe_table`

Shows complete table schema with optional sample data.

**Parameters:**
- `table_name` (required): Table name (format: `schema.table` or `table`)
- `sample_rows` (optional): Number of sample rows (default: 10, max: 50)

**Example:**
```
Describe the dbo.Users table with 5 sample rows
```

#### `execute_query`

Executes SELECT queries with safety checks.

**Parameters:**
- `query` (required): SQL SELECT query

**Example:**
```
Execute: SELECT TOP 20 * FROM Products WHERE Price > 100
```

#### `get_table_relationships`

Shows foreign key relationships for a table.

**Parameters:**
- `table_name` (required): Table name

**Example:**
```
Show relationships for OrderDetails table
```

#### `get_table_indexes`

Shows all indexes on a table with type, columns, uniqueness and fill factor.

**Parameters:**
- `table_name` (required): Table name (format: `schema.table` or `table`)

**Example:**
```
Show indexes for the Orders table
```

#### `search_columns`

Searches for columns by name across the entire database, with wildcard support.

**Parameters:**
- `column_pattern` (required): Search pattern (supports `*` and `?` wildcards, e.g. `*email*`, `user_*`)
- `schema_filter` (optional): Filter by specific schema

**Example:**
```
Find all columns containing "email" in their name
```

#### `get_table_statistics`

Shows per-column statistics: distinct values, NULL count, min/max for numeric and date columns.

**Parameters:**
- `table_name` (required): Table name (format: `schema.table` or `table`)

**Example:**
```
Show statistics for the Customers table
```

#### `get_views`

Lists all database views with optional SQL definitions.

**Parameters:**
- `schema_filter` (optional): Filter by specific schema
- `include_definition` (optional): Include SQL definition (default: true)

**Example:**
```
List all views in the dbo schema
```

### Available Resources

MCP Resources provide read-only context data that clients can retrieve automatically.

#### `db://schema/overview`

Full database schema overview — all accessible tables with columns, types and primary keys.

**Example:**
```
Show me the database schema overview
```

#### `db://schema/tables/{table_name}`

Detailed schema for a single table via URI template.

**Example URI:** `db://schema/tables/dbo.Orders`

---

### Available Prompts

MCP Prompts are pre-built templates that guide the AI through structured workflows.

#### `/analyze-table`

Analyzes a table's structure, types, relationships and suggests improvements.

**Arguments:**
- `table_name` (required): Table name (format: `schema.table` or `table`)

**Example:**
```
/analyze-table table_name=dbo.Orders
```

#### `/query-builder`

Helps build a SELECT query from a natural language description.

**Arguments:**
- `description` (required): What you're looking for in plain language
- `tables` (optional): Tables to use, comma-separated

**Example:**
```
/query-builder description="monthly order totals for 2026" tables="Orders,Customers"
```

#### `/data-dictionary`

Generates a complete data dictionary for one or more tables.

**Arguments:**
- `tables` (optional): Tables to document, comma-separated (empty = all accessible tables)

**Example:**
```
/data-dictionary tables="Orders,Customers,Products"
```

## Security

### Connection String Security

**Recommended: Use Windows Authentication (Windows only)**
```env
SQL_CONNECTION_STRING=Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=MyDB;Trusted_Connection=yes
```

**Azure SQL with AAD:**
```env
SQL_CONNECTION_STRING=Driver={ODBC Driver 17 for SQL Server};Server=myserver.database.windows.net;Database=MyDB;Authentication=ActiveDirectoryInteractive
```

### Table Blacklist

Supports wildcards for pattern matching:

```env
# Block specific tables
BLACKLIST_TABLES=sys_logs,audit_trail

# Block patterns
BLACKLIST_TABLES=sys_*,*_temp,internal_*

# Block with schema
BLACKLIST_TABLES=dbo.sensitive_*,admin.*
```

### Schema Whitelist

Restrict access to specific schemas (case-insensitive matching):

```env
# Only allow these schemas
ALLOWED_SCHEMAS=dbo,sales,hr

# Empty = all schemas allowed
ALLOWED_SCHEMAS=
```

### Query Validation

The server automatically blocks:
- Non-SELECT statements (INSERT, UPDATE, DELETE, DROP, etc.)
- SQL injection patterns
- SQL comments (`--`, `/* */`)
- Dangerous functions (`xp_cmdshell`, `sp_executesql`)
- System stored procedures

### Best Practices

1. **Never commit credentials** - `.env` is in `.gitignore`
2. **Use least privilege** - Create a dedicated read-only SQL user
3. **Enable logging** - Set `LOG_LEVEL=INFO` or `DEBUG` for monitoring
4. **Set appropriate limits** - Configure `MAX_ROWS` and `QUERY_TIMEOUT`
5. **Use schema whitelist** - Restrict access to specific schemas only

See [SECURITY.md](SECURITY.md) for detailed security guidelines.

## Architecture

### Connection Pooling

- Maintains a pool of reusable database connections
- Configurable size: `POOL_SIZE` (default: 5)
- Automatic reconnection for dead connections
- Automatic transaction rollback on release

### Security Validator

Multi-layered query validation (applied in order):
1. **Length cap**: Rejects queries exceeding 4096 characters (DoS prevention)
2. **Null-byte rejection**: Blocks null bytes before normalisation
3. **Unicode / whitespace normalisation**: Collapses whitespace, replaces full-width lookalike characters
4. **SELECT-only enforcement**: Only SELECT statements are allowed
5. **Injection pattern detection**: Regex-based detection of semicolons, comments, UNION, EXEC(), encoding tricks, timing attacks, etc.
6. **Dangerous keyword check**: Word-boundary match against DML/DDL/admin keywords

Additional layers for table access:
- **Blacklist matching**: Pattern-based table filtering with wildcards
- **Schema whitelist**: Case-insensitive schema restriction
- **Identifier validation**: Regex validation of table/schema names to prevent injection

### Error Handling

Stratified error management:
- `TimeoutError`: Pool exhausted or slow queries
- `pyodbc.Error`: Database-specific errors (connection, syntax, permissions)
- `Exception`: Generic fallback with full stack trace logging

All connection pool errors are now logged with specific exception types (no silent failures).
Query timeout is enforced at the cursor level via `cursor.timeout`.

## Testing

### Connection Test

```bash
python test_connection.py
```

Runs 6 automated tests:
1. pyodbc installation check
2. ODBC driver verification
3. Connection string validation
4. Database connection test
5. Basic query execution
6. MCP package verification

### Manual Testing

```bash
# Test server startup (should wait for stdin)
python -m mcp_sqlserver.server

# Test with MCP Inspector (requires Node.js)
npx @modelcontextprotocol/inspector python -m mcp_sqlserver.server
```

## Troubleshooting

### "Data source name not found"

**Solution:** Verify ODBC driver is installed:
```bash
python -c "import pyodbc; print(pyodbc.drivers())"
```

Update connection string with correct driver name (e.g., `ODBC Driver 18 for SQL Server`).

### "Timeout acquiring connection from pool"

**Solution:** Increase pool settings in `.env`:
```env
POOL_SIZE=10
POOL_TIMEOUT=60
```

### "Access denied: Schema 'xyz' not authorized"

**Solution:** Add schema to whitelist:
```env
ALLOWED_SCHEMAS=dbo,xyz
```

### Enable Debug Logging

For detailed troubleshooting:
```env
LOG_LEVEL=DEBUG
```

View logs in Claude Desktop: **Help → Show Logs**

## Development

### Project Structure

```
mcp-sqlserver/
├── src/mcp_sqlserver/
│   ├── __init__.py
│   ├── server.py          # MCP app setup, tool routing, entry point
│   ├── config.py          # CLI args, env vars, global settings
│   ├── security.py        # SecurityValidator, dangerous keywords & patterns
│   ├── pool.py            # ConnectionPool with auto-reconnection
│   ├── helpers.py         # Output formatting (Markdown tables)
│   ├── resources.py       # MCP Resources (schema overview, table schema)
│   ├── prompts.py         # MCP Prompts (analyze-table, query-builder, data-dictionary)
│   └── tools/
│       ├── __init__.py    # Re-exports all tool handlers
│       ├── list_tables.py
│       ├── describe_table.py
│       ├── execute_query.py
│       ├── relationships.py
│       ├── indexes.py
│       ├── search_columns.py
│       ├── statistics.py
│       └── views.py
├── manager/               # SQL MCP Manager — local web UI
│   ├── __init__.py
│   ├── server.py          # FastAPI app: API routes + serve index.html
│   ├── config_manager.py  # Read/write claude_desktop_config.json (atomic)
│   ├── connection_tester.py  # Test a connection string via pyodbc
│   └── static/
│       └── index.html     # Single-page app (vanilla HTML/CSS/JS)
├── tests/
│   ├── test_security_validator.py   # Unit tests for SecurityValidator & helpers
│   ├── test_config_manager.py       # Unit tests for config_manager
│   ├── test_connection_tester.py    # Unit tests for connection_tester
│   └── test_api.py                  # API tests via FastAPI TestClient
├── .env.example           # Environment template
├── pyproject.toml         # Package configuration
├── README.md              # This file
├── CLAUDE_CODE_USAGE.md   # Claude Code integration guide
├── SECURITY.md            # Security best practices
├── CONTRIBUTING.md        # Contribution guidelines
├── LICENSE                # MIT License
└── test_connection.py     # Connection test script
```

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev,manager]"

# Run all unit tests (no database required)
pytest tests/ -v
```

The unit test suite covers:
- `test_security_validator.py` — table access validation, query injection patterns, SQL helpers
- `test_config_manager.py` — config read/write/parse, atomic writes, multi-platform paths
- `test_connection_tester.py` — pyodbc connection test (mocked)
- `test_api.py` — all FastAPI endpoints via TestClient (mocked config_manager)

### Code Quality

```bash
# Linting
pip install ruff
ruff check src/

# Formatting
ruff format src/
```

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone repository
git clone https://github.com/Attilio81/MCP-Sql-Server.git
cd MCP-Sql-Server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Roadmap

- [ ] PostgreSQL support
- [ ] MySQL/MariaDB support
- [ ] Query result caching
- [ ] Data export (CSV, JSON, Excel)
- [ ] ER diagram visualization
- [ ] Query performance statistics
- [ ] Async query execution
- [ ] Multi-database support in single server

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [Model Context Protocol](https://modelcontextprotocol.io/)
- Powered by [pyodbc](https://github.com/mkleehammer/pyodbc)
- Inspired by the [MCP Servers](https://github.com/modelcontextprotocol/servers) project

## Support

- **Documentation**: See documentation files in this repository
- **Issues**: [GitHub Issues](https://github.com/Attilio81/MCP-Sql-Server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Attilio81/MCP-Sql-Server/discussions)

## Related Projects

- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [Claude Desktop](https://claude.ai/download)
- [Claude Code](https://docs.anthropic.com/claude/docs/claude-code)

---

Made with ❤️ for the Claude community
