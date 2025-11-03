# Uso con Claude Code

Questo server MCP può essere utilizzato sia con **Claude Desktop** che con **Claude Code** (CLI).

## Configurazione per Claude Code

### Opzione 1: Configurazione per Progetto

Crea un file `.claude/mcp.json` nella directory del tuo progetto:

```json
{
  "mcpServers": {
    "sqlserver-transito": {
      "command": "python",
      "args": ["-m", "mcp_sqlserver.server"],
      "env": {
        "SQL_CONNECTION_STRING": "Driver={ODBC Driver 17 for SQL Server};Server=Egmsql2019,1433;Database=TRANSITO;UID=sa;PWD=Egm.sistemi",
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

✅ **Questo è già configurato in questo progetto!** Vedi `.claude/mcp.json`

### Opzione 2: Configurazione Globale

Puoi anche configurarlo globalmente per usarlo in qualsiasi progetto:

**Windows:**
```
%APPDATA%\.claude\mcp.json
```

**Linux/macOS:**
```
~/.config/claude/mcp.json
```

## Attivazione

Dopo aver creato/modificato `mcp.json`:

1. **Chiudi la sessione corrente di Claude Code**
2. **Riavvia Claude Code nella directory del progetto**
3. Il server MCP sarà automaticamente caricato

## Verifica Caricamento

Claude Code mostrerà un messaggio all'avvio se il server MCP è stato caricato con successo:

```
🔌 MCP Server loaded: sqlserver-transito
```

Se non vedi questo messaggio, controlla:
- Il file `.claude/mcp.json` esiste ed è valido JSON
- Python è disponibile nel PATH
- Il package `mcp-sqlserver` è installato: `pip list | grep mcp-sqlserver`

## Utilizzo con Claude Code

Una volta caricato, puoi chiedere a Claude Code di usare il server MCP:

### Esempi di Prompt

**1. Esplorare il database:**
```
Usa il server MCP SQL Server per mostrarmi tutte le tabelle del database
```

**2. Analizzare una tabella:**
```
Descrivi la struttura della tabella anagrax usando il server MCP
```

**3. Query dati:**
```
Usa il server MCP per trovare tutti i record nella tabella leadsx
```

**4. Analisi relazioni:**
```
Mostrami le foreign keys della tabella movoffx usando il tool MCP
```

## Tool MCP Disponibili

Quando chiedi a Claude Code di usare il server MCP, avrà accesso a questi tool:

### `list_tables`
Elenca tutte le tabelle accessibili con metriche (righe, dimensioni)

**Esempio:**
```
Elenca tutte le tabelle del database usando list_tables
```

### `describe_table`
Mostra schema completo di una tabella con esempi

**Parametri:**
- `table_name`: Nome tabella (es. "dbo.anagrax")
- `sample_rows`: Numero righe esempio (default: 10, max: 50)

**Esempio:**
```
Usa describe_table per mostrare la struttura di anagrax con 5 righe di esempio
```

### `execute_query`
Esegue query SELECT sicure

**Parametri:**
- `query`: Query SQL (solo SELECT)

**Esempio:**
```
Esegui questa query: SELECT TOP 10 * FROM confx WHERE id > 100
```

### `get_table_relationships`
Mostra foreign keys di una tabella

**Parametri:**
- `table_name`: Nome tabella

**Esempio:**
```
Mostrami le relazioni della tabella movoffx
```

## Vantaggi con Claude Code

### 1. Analisi Automatica
```
Analizza il database TRANSITO e crea un diagramma ER delle relazioni principali
```

### 2. Generazione Codice
```
Guarda la struttura di anagrax e genera una classe Python con SQLAlchemy
```

### 3. Documentazione Automatica
```
Documenta tutte le tabelle del database in un file markdown
```

### 4. Data Analysis
```
Analizza i dati in leadsx e trova pattern o anomalie
```

## Debug

### MCP Server non si carica

**1. Controlla la sintassi JSON:**
```bash
python -c "import json; json.load(open('.claude/mcp.json'))"
```

**2. Testa il server manualmente:**
```bash
python -m mcp_sqlserver.server
```

Dovrebbe rimanere in attesa di input. Premi `Ctrl+C` per uscire.

**3. Verifica le credenziali:**
```bash
python test_connection.py
```

### Timeout o Connessioni Lente

Aumenta i timeout in `.claude/mcp.json`:
```json
{
  "env": {
    "QUERY_TIMEOUT": "60",
    "POOL_TIMEOUT": "60"
  }
}
```

### Password con Caratteri Speciali

Se la password contiene caratteri speciali, assicurati che siano correttamente escaped nel JSON:
- `"` → `\"`
- `\` → `\\`
- `/` → `\/` (opzionale)

## Differenze con Claude Desktop

| Feature | Claude Desktop | Claude Code |
|---------|---------------|-------------|
| Configurazione | `%APPDATA%/Claude/claude_desktop_config.json` | `.claude/mcp.json` o `~/.config/claude/mcp.json` |
| Scope | Globale | Per progetto o globale |
| Riavvio | Riavvia app | Riavvia sessione |
| UI | Interfaccia grafica | CLI/Terminal |
| Use Case | Esplorazione interattiva | Automazione, scripting, analisi |

## Best Practices

### 1. Usa per progetto
Configura `.claude/mcp.json` in ogni progetto che accede al database per mantenere le credenziali isolate.

### 2. Sicurezza
- Non committare `.claude/mcp.json` con credenziali (è già in `.gitignore`)
- Usa variabili d'ambiente per credenziali sensibili:

```json
{
  "mcpServers": {
    "sqlserver": {
      "command": "python",
      "args": ["-m", "mcp_sqlserver.server"],
      "env": {
        "SQL_CONNECTION_STRING": "${SQL_TRANSITO_CONN}"
      }
    }
  }
}
```

### 3. Limiti Appropriati
Per Claude Code (analisi dati più pesanti), considera:
```json
{
  "env": {
    "MAX_ROWS": "500",
    "QUERY_TIMEOUT": "60"
  }
}
```

## Troubleshooting Common Issues

### "Server sqlserver-transito not found"
- Il server non è stato caricato
- Riavvia Claude Code completamente
- Verifica che `.claude/mcp.json` esista e sia valido

### "Connection timeout"
- Il database non è raggiungibile
- Verifica firewall e credenziali
- Aumenta `POOL_TIMEOUT`

### "Package mcp-sqlserver not found"
```bash
cd C:\Progetti Pilota\MCPSqlServer
pip install -e .
```

### "Permission denied"
- L'utente SQL non ha permessi sufficienti
- Verifica GRANT/PERMISSIONS sul database

## Esempi Avanzati

### 1. Reverse Engineering Schema
```
Usa il server MCP per analizzare tutte le tabelle del database e genera:
1. Diagramma ER in Mermaid
2. Script CREATE TABLE equivalenti
3. Documentazione markdown completa
```

### 2. Data Migration Script
```
Analizza le tabelle anagrax e leadsx, poi genera uno script Python
per migrare i dati da SQL Server a PostgreSQL
```

### 3. Data Quality Report
```
Usa il server MCP per controllare:
- Valori NULL in colonne NOT NULL
- Duplicate keys
- Foreign key violations
- Formati dati invalidi

Genera un report con i problemi trovati
```

### 4. API Generator
```
Basandoti sulla struttura delle tabelle, genera un'API REST
con FastAPI che espone endpoint CRUD per ogni tabella
```

## Risorse

- [MCP Documentation](https://modelcontextprotocol.io/)
- [Claude Code Docs](https://docs.claude.com/claude-code)
- [SQL Server ODBC Driver](https://learn.microsoft.com/en-us/sql/connect/odbc/)

## Supporto

Per problemi o domande:
1. Controlla i log: `LOG_LEVEL=DEBUG` in `mcp.json`
2. Testa connessione: `python test_connection.py`
3. Verifica installazione: `pip show mcp-sqlserver`
