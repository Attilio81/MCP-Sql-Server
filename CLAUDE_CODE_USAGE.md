# Using MCP SQL Server with Claude Code

This server works with both **Claude Desktop** and **Claude Code** (CLI).

## Configuration

### Option 1: CLI Arguments (Recommended)

Pass all parameters directly in `.claude/mcp.json` using command-line arguments — no `.env` file needed:

```json
{
  "mcpServers": {
    "sqlserver": {
      "command": "python",
      "args": [
        "-m", "mcp_sqlserver.server",
        "--connection-string", "Driver={ODBC Driver 17 for SQL Server};Server=YOUR_SERVER;Database=YOUR_DB;UID=YOUR_USER;PWD=YOUR_PASSWORD",
        "--max-rows", "100",
        "--query-timeout", "30",
        "--pool-size", "5",
        "--pool-timeout", "30",
        "--blacklist-tables", "",
        "--allowed-schemas", "",
        "--log-level", "INFO"
      ]
    }
  }
}
```

### Option 2: Environment Variables

```json
{
  "mcpServers": {
    "sqlserver": {
      "command": "python",
      "args": ["-m", "mcp_sqlserver.server"],
      "env": {
        "SQL_CONNECTION_STRING": "Driver={ODBC Driver 17 for SQL Server};Server=YOUR_SERVER;Database=YOUR_DB;UID=YOUR_USER;PWD=YOUR_PASSWORD",
        "MAX_ROWS": "100",
        "QUERY_TIMEOUT": "30",
        "POOL_SIZE": "5",
        "POOL_TIMEOUT": "30",
        "BLACKLIST_TABLES": "",
        "ALLOWED_SCHEMAS": "",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

> **Security**: `.claude/mcp.json` is listed in `.gitignore` — never commit it if it contains real credentials.

### Windows Trusted Authentication (no password needed)

```json
"--connection-string", "Driver={ODBC Driver 17 for SQL Server};Server=YOUR_SERVER;Database=YOUR_DB;Trusted_Connection=yes"
```

### Azure SQL

```json
"--connection-string", "Driver={ODBC Driver 17 for SQL Server};Server=YOUR_SERVER.database.windows.net;Database=YOUR_DB;Authentication=ActiveDirectoryInteractive"
```

## Activation

1. Create or edit `.claude/mcp.json` in your project folder
2. Close the current Claude Code session
3. Restart Claude Code in the project directory

Claude Code will show a message at startup if the MCP server loaded successfully.

## Available Tools

### `list_tables`
Lists all accessible tables with metrics (row count, size).

```
List all tables in the database
```

### `describe_table`
Shows complete table schema with optional sample data.

```
Describe the structure of dbo.Orders with 5 sample rows
```

### `execute_query`
Runs safe SELECT queries.

```
Execute: SELECT TOP 10 * FROM Products WHERE Price > 100
```

### `get_table_relationships`
Shows foreign key relationships for a table.

```
Show the foreign key relationships for the Orders table
```

## Advanced Usage Examples

### Reverse Engineering Schema
```
Use the MCP SQL Server tool to analyze all tables and generate:
1. A Mermaid ER diagram
2. Equivalent CREATE TABLE scripts
3. Complete markdown documentation
```

### Generate SQLAlchemy Models
```
Look at the structure of dbo.Users and generate a Python SQLAlchemy model class
```

### Data Analysis
```
Analyze the data in the Orders table and find patterns or anomalies from the last 30 days
```

## Troubleshooting

### MCP server not loading

**1. Check JSON syntax:**
```bash
python -c "import json; json.load(open('.claude/mcp.json'))"
```

**2. Test the server manually:**
```bash
python -m mcp_sqlserver.server --connection-string "Driver={ODBC Driver 17 for SQL Server};Server=YOUR_SERVER;Database=YOUR_DB;Trusted_Connection=yes"
```
The server should wait for stdin input. Press `Ctrl+C` to exit.

**3. Test the connection:**
```bash
python test_connection.py
```

### Timeout or slow connections

Increase timeouts in `.claude/mcp.json`:
```json
"--query-timeout", "60",
"--pool-timeout", "60"
```

### Passwords with special characters

If the password contains special characters, make sure they are properly escaped in the JSON string:
- `"` → `\"`
- `\` → `\\`

### Package not found

```bash
pip install -e .
```

## Comparison: Claude Desktop vs Claude Code

| Feature | Claude Desktop | Claude Code |
|---------|---------------|-------------|
| Config file | `claude_desktop_config.json` | `.claude/mcp.json` |
| Scope | Global | Per-project or global |
| Restart required | Restart app | Restart session |
| Interface | GUI / Terminal | CLI / Terminal |
| Typical use | Interactive exploration | Automation, scripting, analysis |
