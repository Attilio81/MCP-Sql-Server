# Using MCP SQL Server with Claude Code

This server works with both **Claude Desktop** and **Claude Code** (CLI). Since the multi-database rework there is **one server process for all databases**, defined in `~/.mcp_sqlserver/databases.json`.

## How Configuration Works

Three files are involved:

| File | Owner | Content |
|---|---|---|
| `~/.mcp_sqlserver/databases.json` | Manager UI (or hand-edited) | All databases: connection strings, limits, security rules |
| `claude_desktop_config.json` | Synced by the Manager | One `sqlserver` entry: `python -m mcp_sqlserver.server --databases <path>` |
| Claude Code user store | `claude mcp add --scope user` | The same single entry, registered once |

Claude Desktop and Claude Code read from **different stores** — registering in one does not register in the other.

## Recommended Workflow

1. Manage databases in the **Manager UI** (`start-manager.bat` → http://localhost:8090). Every add/edit/delete updates `databases.json` and keeps the Claude Desktop config in sync automatically.
2. Click **"Registra su Claude Code"** once — it runs:
   ```
   claude mcp add sqlserver --scope user -- python -m mcp_sqlserver.server --databases <path>
   ```
   After that, adding or removing databases needs **no further registration**: both clients read `databases.json` at server startup.
3. Restart Claude Desktop (or start a new Claude Code session) to pick up changes.

Manual registration without the Manager:

```bash
claude mcp add sqlserver --scope user -- python -m mcp_sqlserver.server \
  --databases "%USERPROFILE%\.mcp_sqlserver\databases.json"

# Verify
claude mcp list
```

## Migration from per-database entries

Old setups had one MCP entry per database (`dbSales`, `dbWarehouse`, ...). Opening the Manager migrates the Claude Desktop entries automatically into `databases.json`. For Claude Code, remove the old entries and add the single one:

```bash
claude mcp remove dbSales --scope user
claude mcp remove dbWarehouse --scope user
claude mcp add sqlserver --scope user -- python -m mcp_sqlserver.server --databases "<path>"
```

## Usage in Claude Code

Every tool takes a `database` parameter with the configured names as enum — just name the database in your request:

```
"On the sales database, list all tables"
"Compare order counts between sales and warehouse"
```

Single-database mode (`--connection-string`, no `--databases`) still works; the `database` parameter is optional there.
