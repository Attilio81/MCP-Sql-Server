# Using MCP SQL Server with Claude Code

This server works with both **Claude Desktop** and **Claude Code** (CLI).

## How Configuration Works: Two Separate Stores

Claude Desktop and Claude Code read from **different configuration files**. It is important to understand this distinction:

| Client | Config file | Scope |
|--------|------------|-------|
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` (Windows) | Global, all projects |
| Claude Code (user) | Claude Code's own user store (via `claude mcp add --scope user`) | Global, all projects |
| Claude Code (project) | `.claude/mcp.json` in the project folder | Per-project only |

The **SQL MCP Manager** web UI reads and writes **only** `claude_desktop_config.json`. It does not read Claude Code's user-scope store.

### The CC Button in the Manager

Each server card in the Manager has a **CC** button. Clicking it runs:

```
claude mcp add <name> --scope user -- python -m mcp_sqlserver.server --connection-string "..." [opts]
```

This registers the server in Claude Code's **user-global** store, making it available in every Claude Code session on the machine.

**Important:** A server registered via CC only (without first being added in the Manager) will **not** appear in the Manager — because the Manager only reads `claude_desktop_config.json`.

### Recommended Workflow

To have a server available in **both** Claude Desktop and Claude Code:

1. **Add it in the Manager** → stored in `claude_desktop_config.json` → available in Claude Desktop after restart
2. **Click CC** on that card → runs `claude mcp add --scope user` → available in Claude Code immediately

Both steps are required if you want the server in both clients.

---

## Claude Code Configuration Options

### Option 1: Via Manager (Recommended)

Use the Manager UI to add/edit connections. Then click **CC** to register in Claude Code. This keeps the single source of truth in `claude_desktop_config.json` and syncs to Claude Code on demand.

### Option 2: `claude mcp add` command (CLI)

Register directly from the terminal without the Manager:

```bash
# User scope (available in all projects, all sessions)
claude mcp add dbVittone --scope user -- python -m mcp_sqlserver.server \
  --connection-string "Driver={ODBC Driver 17 for SQL Server};Server=MYSERVER;Database=MYDB;Trusted_Connection=yes" \
  --max-rows 100 \
  --query-timeout 30

# Project scope (stored in .claude/mcp.json, per-project)
claude mcp add dbVittone --scope project -- python -m mcp_sqlserver.server \
  --connection-string "Driver={ODBC Driver 17 for SQL Server};Server=MYSERVER;Database=MYDB;Trusted_Connection=yes"

# List all registered MCP servers
claude mcp list

# Remove a server
claude mcp remove dbVittone --scope user
```

### Option 3: Manual `.claude/mcp.json` (per-project)

Create `.claude/mcp.json` in your project folder (already in `.gitignore`):

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
        "--log-level", "INFO"
      ]
    }
  }
}
```

> **Security**: `.claude/mcp.json` is listed in `.gitignore` — never commit it if it contains real credentials.

### Option 4: Environment Variables

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
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### Windows Trusted Authentication (no password needed)

```json
"--connection-string", "Driver={ODBC Driver 17 for SQL Server};Server=YOUR_SERVER;Database=YOUR_DB;Trusted_Connection=yes"
```

### Azure SQL

```json
"--connection-string", "Driver={ODBC Driver 17 for SQL Server};Server=YOUR_SERVER.database.windows.net;Database=YOUR_DB;Authentication=ActiveDirectoryInteractive"
```

---

## Activation

**User-scope servers** (`--scope user`) are active immediately in any new Claude Code session — no restart needed.

**Project-scope servers** (`.claude/mcp.json`):
1. Create or edit `.claude/mcp.json` in your project folder
2. Close the current Claude Code session
3. Restart Claude Code in the project directory

Claude Code will show a message at startup if the MCP server loaded successfully.

---

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

---

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

---

## Troubleshooting

### MCP server not loading

**1. List registered servers and verify:**
```bash
claude mcp list
```

**2. Check JSON syntax (if using .claude/mcp.json):**
```bash
python -c "import json; json.load(open('.claude/mcp.json'))"
```

**3. Test the server manually:**
```bash
python -m mcp_sqlserver.server --connection-string "Driver={ODBC Driver 17 for SQL Server};Server=YOUR_SERVER;Database=YOUR_DB;Trusted_Connection=yes"
```
The server should wait for stdin input. Press `Ctrl+C` to exit.

**4. Test the connection:**
```bash
python test_connection.py
```

### Timeout or slow connections

Increase timeouts:
```
--query-timeout 60
--pool-timeout 60
```

### Passwords with special characters

If the password contains special characters, make sure they are properly escaped in the JSON string:
- `"` → `\"`
- `\` → `\\`

### Package not found

```bash
pip install -e .
```

### Server visible in Claude Code but not in Manager

The server was registered via `claude mcp add --scope user` (or via CC button) without also being added in the Manager. The Manager only reads `claude_desktop_config.json`.

**Fix:** Add the server in the Manager manually (Edit → Save), then click CC to re-sync it to Claude Code.

---

## Comparison: Claude Desktop vs Claude Code

| Feature | Claude Desktop | Claude Code (user) | Claude Code (project) |
|---------|---------------|-------------------|-----------------------|
| Config file | `claude_desktop_config.json` | Claude Code user store | `.claude/mcp.json` |
| Managed by | SQL MCP Manager UI | CC button or `claude mcp add` | Manual or `claude mcp add --scope project` |
| Scope | Global (all sessions) | Global (all projects) | Per-project only |
| Restart required | Restart app | No | Restart session |
| Interface | GUI / Terminal | CLI / Terminal | CLI / Terminal |
| Typical use | Interactive exploration | All projects, always available | Project-specific databases |
