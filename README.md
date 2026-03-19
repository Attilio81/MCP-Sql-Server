# MCP SQL Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-1.0-green.svg)](https://modelcontextprotocol.io/)

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
| `--log-level` | `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

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

Restrict access to specific schemas:

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

Multi-layered validation:
1. **Blacklist matching**: Pattern-based table filtering with wildcards
2. **Schema validation**: Regex validation to prevent SQL injection
3. **Query parsing**: Detection of dangerous keywords and patterns
4. **Identifier validation**: Validates table/column names format

### Error Handling

Stratified error management:
- `TimeoutError`: Pool exhausted or slow queries
- `pyodbc.Error`: Database-specific errors (connection, syntax, permissions)
- `Exception`: Generic fallback with full stack trace logging

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
│   └── server.py          # Main MCP server implementation
├── tests/                 # Unit tests (TODO)
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
pip install pytest pytest-asyncio

# Run tests
pytest tests/
```

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
