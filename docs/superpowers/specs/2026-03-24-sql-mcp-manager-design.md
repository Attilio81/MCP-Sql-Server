# SQL MCP Manager — Design Spec

**Date:** 2026-03-24
**Status:** Approved by user

---

## Overview

A local web-based management UI integrated into the MCP SQL Server repository as a `manager/` subfolder. It allows users to add, edit, delete, and test SQL Server MCP connections, which are persisted directly into Claude's `claude_desktop_config.json` file.

**Entry point:** `python -m manager.server` → starts FastAPI on `http://localhost:8090` and auto-opens the browser.

---

## Goals

- CRUD operations on `mcp_sqlserver` entries in `claude_desktop_config.json`
- Test a SQL Server connection (via pyodbc) before or after saving
- Show live connection status (online / offline) for each configured server
- Preserve all other entries in `claude_desktop_config.json` untouched

---

## Architecture

```
manager/
├── __init__.py
├── server.py             # FastAPI app: routes, startup, auto-browser open
├── config_manager.py     # Read/write claude_desktop_config.json
├── connection_tester.py  # Test a connection string via pyodbc
└── static/
    └── index.html        # Single-page app (vanilla HTML + CSS + JS)
```

New dependencies added to `pyproject.toml` as an optional dependency group:

```toml
[project.optional-dependencies]
manager = [
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
]
```

`pyodbc` is already a core dependency — no new package needed for connection testing.

---

## Config File Detection

`config_manager.py` auto-detects the Claude Desktop config path by platform:

| Platform | Path |
|----------|------|
| Windows  | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS    | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux    | `~/.config/Claude/claude_desktop_config.json` |

The manager only reads and writes keys under `mcpServers` where the `args` array contains the string `"mcp_sqlserver.server"` as a standalone element (i.e., `"mcp_sqlserver.server" in entry["args"]`). The Claude Desktop config format stores args as a JSON array — `["-m", "mcp_sqlserver.server", "--connection-string", "..."]` — so the filter must be an array-element membership check, not a substring search. All other `mcpServers` entries and top-level keys are preserved exactly as-is during every write.

Writes are performed atomically: the updated content is first written to a `.tmp` file alongside the target, then swapped in with `os.replace()`. This prevents config corruption if the process is interrupted mid-write.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/servers` | Returns list of all mcp_sqlserver entries with parsed parameters |
| `POST` | `/api/servers` | Adds a new entry; returns error if name already exists |
| `PUT` | `/api/servers/{name}` | Updates an existing entry by name |
| `DELETE` | `/api/servers/{name}` | Removes an entry by name |
| `POST` | `/api/test` | Tests a connection string via pyodbc; returns `{ok, error}`. Request body: `{"connection_string": "..."}` |

All endpoints return JSON. Errors return `{detail: "..."}` with appropriate HTTP status codes (400, 404, 409, 500).

---

## Data Model

Each MCP server entry is represented internally as:

```json
{
  "name": "db-vendite",
  "connection_string": "Driver={ODBC Driver 17 for SQL Server};Server=srv1;Database=Vendite;Trusted_Connection=yes",
  "max_rows": 100,
  "query_timeout": 30,
  "pool_size": 5,
  "pool_timeout": 30,
  "allowed_schemas": "dbo",
  "blacklist_tables": "sys_*,*_audit",
  "log_level": "INFO"
}
```

`config_manager.py` is responsible for translating between this model and the Claude Desktop config format (`command`, `args` array).

---

## UI (index.html)

Single HTML file with vanilla CSS and JS — no build step, no framework.

**Layout:**
- **Header:** title "SQL MCP Manager" + "Nuova Connessione" button
- **Server list:** one card per configured server
  - Each card shows: status dot (online/offline/unknown), name, server›database, schema tags, max-rows, timeout
  - Card actions: Test (⚡), Edit (✏️), Delete (🗑)
- **Inline form panel:** appears below the list when adding or editing
  - Fields: Name, Connection String (full width), Max Rows, Allowed Schemas, Blacklist Tables, Query Timeout, Pool Size, Pool Timeout
  - Actions: Cancel · Test Connection · Save

**Status indicator behavior:**
- On page load, the UI calls `POST /api/test` for each configured server in parallel
- Dot is grey (unknown) while testing, green (online) on success, red (offline) on failure
- "Test" button on each card re-runs the test for that server only

---

## Error Handling

- If `claude_desktop_config.json` does not exist, the manager shows an empty server list and creates the file on first save
- If the file is malformed JSON, the UI shows an error banner; no write is attempted
- Connection test errors surface the pyodbc error message in the UI (never crash the server)
- Duplicate server name on POST returns HTTP 409

---

## Installation & Usage

```bash
# Install manager dependencies
pip install -e ".[manager]"

# Start the manager
python -m manager.server
# Opens http://localhost:8090 automatically
```

---

## Out of Scope

- Managing non-mcp_sqlserver MCP entries (other tools, other databases)
- Authentication / access control (runs locally only)
- PostgreSQL / MySQL support (future roadmap)
- Export/import of config

---

# Feature: Dizionario Semantico per Server

**Data:** 2026-03-24
**Status:** Draft

---

## Concetto

Ogni server MCP accumula nel tempo una mappa tra linguaggio di business e schema fisico del database. Quando l'utente chiede *"quante vendite ha fatto Mario Rossi?"*, Claude non sa a priori che "Mario Rossi" è in `anagra.cognome + nome`. Dopo aver eseguito le query e trovato la risposta, Claude **scrive questa conoscenza** in un file Markdown dedicato al server.

Alla sessione successiva, Claude **legge il dizionario** e sa già dove cercare — senza dover re-esplorare lo schema.

Il flusso è:

```
Utente chiede X
   → Claude esplora lo schema / esegue query
   → Claude trova il mapping (termine business → tabella/colonna)
   → Claude chiama update_dictionary per salvare la scoperta
   → Sessioni future: Claude legge db://dictionary e già conosce il mapping
```

Il dizionario è un file `.md` umano-leggibile. L'utente può modificarlo manualmente (es. correggere un errore, copiare mappings da un altro server) via Manager UI.

---

## Formato del File Dizionario

Il file è Markdown strutturato con tabelle. Claude deve rispettare questa struttura per garantire leggibilità e aggiornamenti incrementali corretti.

```markdown
# Dizionario Semantico: {nome_database}
> Aggiornato automaticamente da Claude. Modificabile manualmente.

## Entità di Business
| Termine utente | Tabella | Campi chiave | Note |
|----------------|---------|--------------|------|
| cliente | anagra | codice, cognome, nome | chiave primaria: codice |
| articolo | tabArt | codart, descr | |
| agente | agenti | codage, descage | |

## Filtri e Alias
| Espressione utente | SQL equivalente | Note |
|--------------------|-----------------|------|
| "attivo" | stato = 'A' | campo in anagra |
| "anno corrente" | YEAR(data_doc) = YEAR(GETDATE()) | |
| "clienti nuovi" | data_ins >= DATEADD(year,-1,GETDATE()) | |

## Relazioni Notevoli
| Tabella da | Campo | Tabella a | Campo | Descrizione |
|------------|-------|-----------|-------|-------------|
| anagra | codice | ordini | codcli | clienti e loro ordini |
| tabArt | codart | ordini | codart | articoli negli ordini |
```

---

## MCP Server: Modifiche Backend

### Nuovo parametro di configurazione (`config.py`)

```
--dictionary-file PATH   Path del file dizionario (default: semantic_dictionary.md)
DICTIONARY_FILE          Variabile d'ambiente equivalente
```

Il default `semantic_dictionary.md` è relativo alla working directory del processo MCP. Per configurazioni multi-server si raccomanda un path assoluto (es. `C:\dicts\vendite_dictionary.md`).

### MCP Resource: `db://dictionary`

Il dizionario viene esposto come **MCP Resource**, non solo come tool. Questo permette a Claude di caricarlo automaticamente come contesto all'inizio di ogni sessione, senza dover decidere attivamente di chiamare un tool.

```
URI:         db://dictionary
Description: Dizionario semantico del database — mappa tra linguaggio di business e schema fisico
Mime-type:   text/markdown
Behavior:    Se il file non esiste, restituisce stringa vuota (no errore)
```

Implementazione: aggiungere a `resources.py` analogamente alle risorse `db://schema/overview` esistenti.

### MCP Tool: `update_dictionary`

Tool che Claude chiama per **aggiungere o aggiornare una singola riga** in una delle tre sezioni del dizionario. Non sovrascrive il file — legge, aggiorna la riga specifica o aggiunge in fondo alla sezione, riscrive.

**Schema input:**
```json
{
  "section": "entities | filters | relations",
  "key": "valore del primo campo (usato per deduplicazione, es. 'cliente')",
  "row": "riga completa in formato Markdown table (es. '| cliente | anagra | codice, cognome | |')"
}
```

**Comportamento:**
- Se il file non esiste → lo crea con la struttura base
- Se la riga con quel `term` esiste già nella sezione → la sostituisce
- Se non esiste → la aggiunge in fondo alla sezione

**Descrizione del tool per Claude** (istruzioni su *quando* chiamarlo):

> Chiama `update_dictionary` ogni volta che scopri un'associazione non ovvia tra linguaggio di business e schema del database:
> - Quando identifichi quale tabella/colonne corrispondono a un'entità nominata dall'utente (es. "cliente" → `anagra`)
> - Quando apprendi un'espressione filtro ricorrente (es. "attivo" → `stato = 'A'`)
> - Quando scopri una relazione join non deducibile dai nomi delle colonne
>
> Non chiamare `update_dictionary` per informazioni già presenti nel dizionario o per mappings ovvi dal nome della tabella stessa.

**Human-on-the-loop: NO.** Il tool deve essere chiamato silenziosamente senza richiedere conferma all'utente. Claude notifica la scoperta in modo conversazionale (es. *"Ho salvato nel dizionario che 'cliente' corrisponde alla tabella `anagra`"*) ma non attende approvazione. Il Manager UI è il meccanismo di correzione post-hoc se il mapping salvato fosse errato. Richiedere conferma ad ogni discovery interromperebbe il flusso conversazionale in modo inaccettabile.

---

## Manager Backend: Nuovi Endpoint

Questi endpoint leggono il `claude_desktop_config.json` per trovare il `--dictionary-file` associato al server, poi leggono/scrivono quel file.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/dictionary/{server_name}` | Legge e restituisce il contenuto del file `.md` associato al server. Se il file non esiste, restituisce stringa vuota. |
| `POST` | `/api/dictionary/{server_name}` | Riceve `{"content": "..."}` e sovrascrive il file `.md`. |

**Logica GET:**
1. Trova il server `{server_name}` in `claude_desktop_config.json`
2. Cerca `--dictionary-file` negli `args`; se assente usa il default `semantic_dictionary.md`
3. Se il path è relativo, lo risolve relativo alla directory del progetto MCP (directory del `server.py`)
4. Legge e restituisce il contenuto

**Logica POST:**
1. Come sopra per trovare il path
2. Validazione: il path deve restare dentro la directory del progetto (no path traversal)
3. Crea la directory se non esiste
4. Scrive con scrittura atomica (`.tmp` + `os.replace()`)

**Errori:**
- `404` se il server non esiste in config
- `400` se il path risolto è fuori dalla directory consentita

---

## Manager Frontend: UI per il Dizionario

### Pulsante su ogni card

Aggiungere un pulsante `📖` accanto agli esistenti (⚡ Test, ✏️ Edit, 🗑 Delete) su ogni server card.

### Modal Editor

Al click, si apre un modal con:

- **Titolo:** "Dizionario Semantico — {nome_server}"
- **Descrizione:** testo grigio piccolo: *"Questo file viene aggiornato automaticamente da Claude. Puoi modificarlo manualmente o copiare sezioni da altri dizionari."*
- **Textarea:** grande (min 400px), font monospace, mostra il contenuto Markdown corrente
- **Pulsanti:**
  - `Salva` → `POST /api/dictionary/{server_name}` con il contenuto aggiornato
  - `Chiudi` → chiude il modal senza salvare
- **Feedback:** banner verde "Dizionario salvato" / rosso "Errore nel salvataggio"

Il contenuto della textarea è caricato via `GET /api/dictionary/{server_name}` all'apertura del modal (non al caricamento della pagina).

---

## Aggiornamento Data Model

Il data model esistente non cambia struttura. Il `--dictionary-file` è un parametro opzionale del server MCP, gestito come tutti gli altri parametri in `config_manager.py`:

```json
{
  "name": "db-vendite",
  "connection_string": "...",
  "dictionary_file": "C:\\dicts\\vendite_dictionary.md",
  ...
}
```

`config_manager.py` serializza `dictionary_file` come `["--dictionary-file", "path"]` negli `args` e lo deserializza allo stesso modo.

---

## Aggiornamento UI Form (Aggiungi/Modifica Server)

Nel form inline di aggiunta/modifica server, aggiungere un campo opzionale:

- **Label:** "File Dizionario (opzionale)"
- **Placeholder:** `semantic_dictionary.md`
- **Hint:** testo grigio: *"Path del file Markdown in cui Claude accumula la conoscenza semantica del database. Lascia vuoto per usare il default."*

---

## File Map Aggiornata

| Action | Path | Responsabilità |
|--------|------|----------------|
| Modify | `src/mcp_sqlserver/config.py` | Aggiungere `DICTIONARY_FILE` / `--dictionary-file` |
| Modify | `src/mcp_sqlserver/resources.py` | Aggiungere resource `db://dictionary` |
| Create | `src/mcp_sqlserver/tools/dictionary.py` | Tool `update_dictionary` |
| Modify | `src/mcp_sqlserver/tools/__init__.py` | Re-export `handle_update_dictionary` |
| Modify | `src/mcp_sqlserver/server.py` | Registrare tool + dispatch |
| Modify | `manager/server.py` | Aggiungere GET/POST `/api/dictionary/{server_name}` |
| Modify | `manager/config_manager.py` | Serializzare/deserializzare `dictionary_file` |
| Modify | `manager/static/index.html` | Pulsante 📖, modal editor |
| Create | `tests/test_dictionary_tool.py` | Unit test per `update_dictionary` |

---

## Scope Escluso

- Versionamento del dizionario (git history è sufficiente)
- Merge automatico tra dizionari di server diversi
- Ricerca/indicizzazione vettoriale (plain text è sufficiente per il volume atteso)
- Traduzione automatica da italiano a inglese nei termini
