# Semantic Dictionary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-server semantic dictionary that Claude populates automatically as it discovers business-name → table/column mappings, exposed as an MCP Resource (`db://dictionary`) and writable via the `update_dictionary` tool, with Manager UI for manual editing.

> **Design note:** The spec used `term`/`definition`/`note` as tool input fields. This plan deliberately uses `key` (clearer deduplication purpose) and `row` (full markdown table row). The spec has been updated to match.

**Architecture:** MCP server gains `DICTIONARY_FILE` config param, a `db://dictionary` Resource (auto-loaded by Claude), and `update_dictionary` Tool (Claude calls silently when it learns a mapping). Manager FastAPI gets two new endpoints and the frontend gets a 📖 button per card that opens a modal editor.

**Tech Stack:** Python 3.10+, MCP, FastAPI, vanilla HTML/CSS/JS

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `src/mcp_sqlserver/config.py` | Add `DICTIONARY_FILE` global + `--dictionary-file` CLI arg |
| Create | `src/mcp_sqlserver/tools/dictionary.py` | `handle_update_dictionary` + `_upsert_row` logic |
| Modify | `src/mcp_sqlserver/tools/__init__.py` | Re-export `handle_update_dictionary` |
| Modify | `src/mcp_sqlserver/resources.py` | Add `db://dictionary` resource |
| Modify | `src/mcp_sqlserver/server.py` | Import tool, add Tool definition, add dispatch branch |
| Modify | `manager/config_manager.py` | Add `dictionary_file` to serialization + `get_dictionary_path()` |
| Modify | `manager/server.py` | Add `DictionaryContent` model, GET/POST endpoints, `ServerEntry.dictionary_file` |
| Modify | `manager/static/index.html` | Modal CSS/HTML, 📖 button, `openDictionary`/`saveDictionary` JS, form field |
| Create | `tests/test_dictionary.py` | Unit tests for dictionary tool (no DB required) |

---

## Task 1: config.py — Add DICTIONARY_FILE

**Files:**
- Modify: `src/mcp_sqlserver/config.py`

- [ ] **Step 1: Add `--dictionary-file` to `_parse_args()`**

In `_parse_args()`, after the `--log-level` argument, add:

```python
parser.add_argument(
    "--dictionary-file",
    help="Path del file dizionario semantico (default: semantic_dictionary.md)",
)
```

- [ ] **Step 2: Add `DICTIONARY_FILE` to `_load_config()`**

In the `global` declaration at the top of `_load_config()`, add `DICTIONARY_FILE`.

After the `ALLOWED_SCHEMAS` assignment, add:

```python
DICTIONARY_FILE = _args.dictionary_file or os.getenv("DICTIONARY_FILE", "semantic_dictionary.md")
```

- [ ] **Step 3: Add module-level default**

After `ALLOWED_SCHEMAS: list[str] = []`, add:

```python
DICTIONARY_FILE: str = "semantic_dictionary.md"
```

- [ ] **Step 4: Verify the default value is correct**

Run:
```bash
cd C:\Users\attilio.pregnolato.EGMSISTEMI\Documents\GitHub\MCP-Sql-Server
python -c "from mcp_sqlserver import config; print(config.DICTIONARY_FILE)"
```
Expected: `semantic_dictionary.md`

- [ ] **Step 5: Commit**

```bash
git add src/mcp_sqlserver/config.py
git commit -m "feat: add DICTIONARY_FILE config param with --dictionary-file CLI arg"
```

---

## Task 2: tools/dictionary.py — Core Logic (TDD)

**Files:**
- Create: `src/mcp_sqlserver/tools/dictionary.py`
- Create: `tests/test_dictionary.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dictionary.py`:

```python
# -*- coding: utf-8 -*-
"""Unit tests for dictionary tool — no database required."""
import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_sqlserver.tools.dictionary import (
    _DEFAULT_TEMPLATE,
    _upsert_row,
    handle_update_dictionary,
)


# ── _upsert_row unit tests ──────────────────────────────────────────────────

def test_upsert_row_adds_new_entity():
    result = _upsert_row(_DEFAULT_TEMPLATE, "entities", "cliente", "| cliente | anagra | codice, cognome | |")
    assert "| cliente | anagra | codice, cognome | |" in result


def test_upsert_row_replaces_existing_entity():
    base = _upsert_row(_DEFAULT_TEMPLATE, "entities", "cliente", "| cliente | anagra | codice | vecchia |")
    result = _upsert_row(base, "entities", "cliente", "| cliente | anagra | codice, cognome | nuova |")
    assert "vecchia" not in result
    assert "nuova" in result
    assert result.count("| cliente |") == 1


def test_upsert_row_adds_filter():
    result = _upsert_row(_DEFAULT_TEMPLATE, "filters", "attivo", "| attivo | stato = 'A' | campo in anagra |")
    assert "| attivo | stato = 'A' |" in result


def test_upsert_row_adds_relation():
    result = _upsert_row(_DEFAULT_TEMPLATE, "relations", "anagra",
                         "| anagra | codice | ordini | codcli | clienti e ordini |")
    assert "| anagra | codice | ordini |" in result


def test_upsert_row_missing_section_appends_it():
    content = "# Dizionario\n\n## Altra Sezione\n| col |\n|-----|"
    result = _upsert_row(content, "entities", "x", "| x | t | f | |")
    assert "## Entità di Business" in result
    assert "| x | t | f | |" in result


def test_upsert_row_multiple_sections_correct_target():
    """Row added to entities must not appear under filters."""
    result = _upsert_row(_DEFAULT_TEMPLATE, "entities", "cliente", "| cliente | anagra | cod | |")
    filters_start = result.find("## Filtri e Alias")
    entities_start = result.find("## Entità di Business")
    row_pos = result.find("| cliente |")
    assert entities_start < row_pos < filters_start


# ── handle_update_dictionary integration tests ─────────────────────────────

def _run(arguments, dict_path):
    """Run async handler synchronously, patching config.DICTIONARY_FILE."""
    async def _inner():
        with patch("mcp_sqlserver.tools.dictionary.config") as mock_cfg:
            mock_cfg.DICTIONARY_FILE = str(dict_path)
            return await handle_update_dictionary(arguments)
    return asyncio.run(_inner())


def test_handler_creates_file_when_missing(tmp_path):
    path = tmp_path / "dict.md"
    result = _run({"section": "entities", "key": "cliente", "row": "| cliente | anagra | codice | |"}, path)
    assert "✅" in result[0].text
    assert path.exists()
    assert "cliente" in path.read_text(encoding="utf-8")


def test_handler_appends_to_existing_file(tmp_path):
    path = tmp_path / "dict.md"
    path.write_text(_DEFAULT_TEMPLATE, encoding="utf-8")
    _run({"section": "entities", "key": "fornitore", "row": "| fornitore | fornitori | codf | |"}, path)
    assert "fornitore" in path.read_text(encoding="utf-8")


def test_handler_replaces_existing_key(tmp_path):
    path = tmp_path / "dict.md"
    _run({"section": "entities", "key": "cliente", "row": "| cliente | anagra | codice | vecchia |"}, path)
    _run({"section": "entities", "key": "cliente", "row": "| cliente | anagra | codice, nome | nuova |"}, path)
    content = path.read_text(encoding="utf-8")
    assert "vecchia" not in content
    assert "nuova" in content
    assert content.count("| cliente |") == 1


def test_handler_invalid_section(tmp_path):
    path = tmp_path / "dict.md"
    result = _run({"section": "unknown", "key": "x", "row": "| x |"}, path)
    assert "❌" in result[0].text
    assert "unknown" in result[0].text


def test_handler_missing_key(tmp_path):
    path = tmp_path / "dict.md"
    result = _run({"section": "entities", "key": "", "row": "| x |"}, path)
    assert "❌" in result[0].text


def test_handler_missing_row(tmp_path):
    path = tmp_path / "dict.md"
    result = _run({"section": "entities", "key": "x", "row": ""}, path)
    assert "❌" in result[0].text
```

- [ ] **Step 2: Run tests to verify they all fail**

```bash
pytest tests/test_dictionary.py -v
```
Expected: all FAILED with ImportError (module doesn't exist yet).

- [ ] **Step 3: Create `src/mcp_sqlserver/tools/dictionary.py`**

```python
# -*- coding: utf-8 -*-
"""Tool handler: update_dictionary — saves semantic mappings to the dictionary file."""

import re
import logging
from pathlib import Path

from mcp.types import TextContent

from mcp_sqlserver import config

logger = logging.getLogger(__name__)

SECTION_HEADERS = {
    "entities": "## Entità di Business",
    "filters": "## Filtri e Alias",
    "relations": "## Relazioni Notevoli",
}

SECTION_TABLE_HEADERS = {
    "entities": (
        "| Termine utente | Tabella | Campi chiave | Note |\n"
        "|----------------|---------|--------------|------|"
    ),
    "filters": (
        "| Espressione utente | SQL equivalente | Note |\n"
        "|--------------------|-----------------|------|"
    ),
    "relations": (
        "| Tabella da | Campo | Tabella a | Campo | Descrizione |\n"
        "|------------|-------|-----------|-------|-------------|"
    ),
}

_DEFAULT_TEMPLATE = """\
# Dizionario Semantico
> Aggiornato automaticamente da Claude. Modificabile manualmente.

## Entità di Business
| Termine utente | Tabella | Campi chiave | Note |
|----------------|---------|--------------|------|

## Filtri e Alias
| Espressione utente | SQL equivalente | Note |
|--------------------|-----------------|------|

## Relazioni Notevoli
| Tabella da | Campo | Tabella a | Campo | Descrizione |
|------------|-------|-----------|-------|-------------|
"""


async def handle_update_dictionary(arguments: dict) -> list[TextContent]:
    """Add or update a row in the semantic dictionary file.

    Called by Claude every time it discovers a non-obvious mapping between
    business language and the physical database schema. Does NOT require
    user confirmation — notify the user conversationally after calling this.

    Arguments:
      section: "entities" | "filters" | "relations"
      key:     first-column value, used for deduplication (e.g. "cliente")
      row:     complete markdown table row (e.g. "| cliente | anagra | codice, cognome | |")

    Row formats by section:
      entities:  | termine utente | tabella | campi chiave | note |
      filters:   | espressione utente | sql equivalente | note |
      relations: | tabella da | campo | tabella a | campo | descrizione |
    """
    section = (arguments.get("section") or "").strip()
    key = (arguments.get("key") or "").strip()
    row = (arguments.get("row") or "").strip()

    if section not in SECTION_HEADERS:
        return [TextContent(
            type="text",
            text=f"❌ Sezione non valida: '{section}'. Valori consentiti: entities, filters, relations",
        )]
    if not key:
        return [TextContent(type="text", text="❌ 'key' è obbligatorio")]
    if not row:
        return [TextContent(type="text", text="❌ 'row' è obbligatorio")]

    dict_path = Path(config.DICTIONARY_FILE)

    if dict_path.exists():
        content = dict_path.read_text(encoding="utf-8")
    else:
        content = _DEFAULT_TEMPLATE
        dict_path.parent.mkdir(parents=True, exist_ok=True)

    updated = _upsert_row(content, section, key, row)
    dict_path.write_text(updated, encoding="utf-8")

    logger.info("Dizionario aggiornato: sezione=%s key=%s", section, key)
    return [TextContent(type="text", text=f"✅ Dizionario aggiornato: '{key}' salvato in '{section}'")]


def _upsert_row(content: str, section: str, key: str, row: str) -> str:
    """Insert or replace a row in the given section. Returns updated content string."""
    section_header = SECTION_HEADERS[section]
    lines = content.splitlines(keepends=True)

    # Find the section header line index
    sec_idx = next(
        (i for i, ln in enumerate(lines) if ln.rstrip() == section_header),
        None,
    )
    if sec_idx is None:
        # Section not found — append it with header and the new row
        table_hdr = SECTION_TABLE_HEADERS[section]
        suffix = f"\n{section_header}\n{table_hdr}\n{row}\n"
        return content.rstrip("\n") + "\n" + suffix

    # Find the end of this section (next "## " header or EOF)
    end_idx = len(lines)
    for i in range(sec_idx + 1, len(lines)):
        if lines[i].startswith("## "):
            end_idx = i
            break

    # Search for existing row matching this key (first cell match)
    key_pat = re.compile(r"^\|\s*" + re.escape(key) + r"\s*\|")
    replace_idx = None
    last_table_idx = sec_idx  # track last "|" line for append position

    for i in range(sec_idx, end_idx):
        stripped = lines[i].rstrip("\r\n")
        if key_pat.match(stripped):
            replace_idx = i
        if stripped.startswith("|"):
            last_table_idx = i

    row_line = row + "\n"
    if replace_idx is not None:
        lines[replace_idx] = row_line
    else:
        lines.insert(last_table_idx + 1, row_line)

    return "".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_dictionary.py -v
```
Expected: all PASSED (9 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mcp_sqlserver/tools/dictionary.py tests/test_dictionary.py
git commit -m "feat: add update_dictionary tool with upsert logic"
```

---

## Task 3: tools/__init__.py — Re-export

**Files:**
- Modify: `src/mcp_sqlserver/tools/__init__.py`

- [ ] **Step 1: Add import and __all__ entry**

Add at the end of the imports:
```python
from mcp_sqlserver.tools.dictionary import handle_update_dictionary
```

Add `"handle_update_dictionary"` to `__all__`.

- [ ] **Step 2: Verify import works**

```bash
python -c "from mcp_sqlserver.tools import handle_update_dictionary; print('OK')"
```
Expected: `OK`

---

## Task 4: resources.py — db://dictionary Resource

**Files:**
- Modify: `src/mcp_sqlserver/resources.py`

- [ ] **Step 1: Add `db://dictionary` to `list_resources()`**

In `list_resources()`, add after the existing `db://schema/overview` resource:

```python
Resource(
    uri="db://dictionary",
    name="semantic-dictionary",
    title="Semantic Dictionary",
    description=(
        "Dizionario semantico del database: mappa tra linguaggio di business e schema fisico. "
        "Carica questa risorsa all'inizio della sessione per conoscere le associazioni già scoperte "
        "(termini utente → tabelle/colonne, filtri comuni, relazioni notevoli)."
    ),
    mimeType="text/markdown",
),
```

- [ ] **Step 2: Add handler in `read_resource()`**

After the `db://schema/overview` branch, add:

```python
if uri_str == "db://dictionary":
    return _read_dictionary()
```

- [ ] **Step 3: Add `_read_dictionary()` helper**

Add at the bottom of the file (after `_read_table_schema`):

```python
def _read_dictionary() -> str:
    """Return the semantic dictionary file contents, or empty string if not created yet."""
    from pathlib import Path
    dict_path = Path(config.DICTIONARY_FILE)
    if not dict_path.exists():
        return ""
    return dict_path.read_text(encoding="utf-8")
```

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all PASSED (no regressions).

- [ ] **Step 5: Commit**

```bash
git add src/mcp_sqlserver/resources.py src/mcp_sqlserver/tools/__init__.py
git commit -m "feat: add db://dictionary MCP resource"
```

---

## Task 5: server.py — Wire update_dictionary Tool

**Files:**
- Modify: `src/mcp_sqlserver/server.py`

- [ ] **Step 1: Import the handler**

In the imports block, add `handle_update_dictionary` to the existing tools import:

```python
from mcp_sqlserver.tools import (
    handle_list_tables,
    handle_describe_table,
    handle_execute_query,
    handle_table_relationships,
    handle_table_indexes,
    handle_search_columns,
    handle_table_statistics,
    handle_get_views,
    handle_update_dictionary,
)
```

- [ ] **Step 2: Add Tool definition in `list_tools()`**

Add at the end of the returned list, before the closing `]`:

```python
Tool(
    name="update_dictionary",
    title="Update Semantic Dictionary",
    description=(
        "Salva una nuova scoperta semantica nel dizionario del database. "
        "Chiama questo tool ogni volta che scopri un'associazione non ovvia tra linguaggio di business "
        "e schema fisico:\n"
        "- Quando identifichi quale tabella/colonne corrispondono a un'entità nominata dall'utente "
        "(es. 'cliente' → tabella `anagra`)\n"
        "- Quando apprendi un'espressione filtro ricorrente (es. 'attivo' → `stato = 'A'`)\n"
        "- Quando scopri una relazione join non deducibile dai nomi delle colonne\n\n"
        "Non chiamare per informazioni già nel dizionario o per mappings ovvi dal nome della tabella. "
        "Notifica sempre l'utente dopo aver salvato (es. 'Ho salvato nel dizionario che ...').\n\n"
        "Row formats:\n"
        "  entities:  | termine utente | tabella | campi chiave | note |\n"
        "  filters:   | espressione utente | sql equivalente | note |\n"
        "  relations: | tabella da | campo | tabella a | campo | descrizione |"
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "section": {
                "type": "string",
                "enum": ["entities", "filters", "relations"],
                "description": "Categoria: entities (termini→tabelle), filters (espressioni→SQL), relations (join tra tabelle)",
            },
            "key": {
                "type": "string",
                "description": "Valore del primo campo della riga (usato per deduplicazione, es. 'cliente')",
            },
            "row": {
                "type": "string",
                "description": "Riga completa in formato Markdown table, es. '| cliente | anagra | codice, cognome | |'",
            },
        },
        "required": ["section", "key", "row"],
    },
),
```

- [ ] **Step 3: Add dispatch branch in `call_tool()`**

In `call_tool()`, after the `elif name == "get_views":` branch, add:

```python
elif name == "update_dictionary":
    content = await handle_update_dictionary(arguments)
```

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/mcp_sqlserver/server.py
git commit -m "feat: register update_dictionary tool in MCP server"
```

---

## Task 6: config_manager.py — dictionary_file Serialization

**Files:**
- Modify: `manager/config_manager.py`

- [ ] **Step 1: Write failing tests**

Add these tests to `tests/test_config_manager.py` (read the file first to find a good insertion point after existing tests):

```python
# ── dictionary_file serialization ──────────────────────────────────────────

def test_serialize_entry_includes_dictionary_file():
    entry = {
        "name": "db-test",
        "connection_string": "Driver=...;Server=s;Database=d;",
        "dictionary_file": "/tmp/my_dict.md",
    }
    result = _serialize_entry(entry)
    assert "--dictionary-file" in result["args"]
    idx = result["args"].index("--dictionary-file")
    assert result["args"][idx + 1] == "/tmp/my_dict.md"


def test_serialize_entry_omits_empty_dictionary_file():
    entry = {
        "name": "db-test",
        "connection_string": "Driver=...;Server=s;Database=d;",
        "dictionary_file": "",
    }
    result = _serialize_entry(entry)
    assert "--dictionary-file" not in result["args"]


def test_parse_entry_reads_dictionary_file():
    args = ["-m", "mcp_sqlserver.server", "--connection-string", "cs", "--dictionary-file", "/tmp/d.md"]
    result = _parse_entry("srv", args)
    assert result["dictionary_file"] == "/tmp/d.md"


def test_get_dictionary_path_default(tmp_path):
    """Returns default path when dictionary_file not set."""
    config_data = {
        "mcpServers": {
            "db-test": {
                "command": "python",
                "args": ["-m", "mcp_sqlserver.server", "--connection-string", "cs"],
            }
        }
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data))
    path = get_dictionary_path("db-test", config_file)
    assert path.name == "semantic_dictionary.md"


def test_get_dictionary_path_absolute(tmp_path):
    """Returns absolute path as-is."""
    abs_path = str(tmp_path / "my_dict.md")
    config_data = {
        "mcpServers": {
            "db-test": {
                "command": "python",
                "args": ["-m", "mcp_sqlserver.server", "--connection-string", "cs",
                         "--dictionary-file", abs_path],
            }
        }
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data))
    result = get_dictionary_path("db-test", config_file)
    assert result == Path(abs_path)


def test_get_dictionary_path_unknown_server(tmp_path):
    config_data = {"mcpServers": {}}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data))
    with pytest.raises(KeyError):
        get_dictionary_path("nonexistent", config_file)
```

Add `get_dictionary_path` to the existing import block in `test_config_manager.py` (lines 5-14). The file already imports `_serialize_entry` and `_parse_entry` — only add the new symbol:

```python
from manager.config_manager import (
    detect_config_path,
    read_config,
    list_servers,
    add_server,
    update_server,
    delete_server,
    _parse_entry,
    _serialize_entry,
    get_dictionary_path,   # ← add this line
)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config_manager.py -v -k "dictionary"
```
Expected: FAILED (function not found or missing field).

- [ ] **Step 3: Update `_serialize_entry()` in config_manager.py**

In `_serialize_entry`, add `"dictionary_file": "--dictionary-file"` to `field_to_flag`:

```python
field_to_flag = {
    "connection_string": "--connection-string",
    "max_rows": "--max-rows",
    "query_timeout": "--query-timeout",
    "pool_size": "--pool-size",
    "pool_timeout": "--pool-timeout",
    "allowed_schemas": "--allowed-schemas",
    "blacklist_tables": "--blacklist-tables",
    "log_level": "--log-level",
    "dictionary_file": "--dictionary-file",
}
```

- [ ] **Step 4: Add `get_dictionary_path()` function**

Add at the end of `config_manager.py`:

```python
def get_dictionary_path(server_name: str, config_path: Optional[Path] = None) -> Path:
    """Return the resolved Path of the dictionary file for the given server.

    Relative paths are resolved relative to the project root (parent of manager/).
    Absolute paths are returned as-is.
    Raises KeyError if the server is not found.
    """
    servers = list_servers(config_path)
    entry = next((s for s in servers if s["name"] == server_name), None)
    if entry is None:
        raise KeyError(f"Server '{server_name}' not found")
    raw = entry.get("dictionary_file") or "semantic_dictionary.md"
    p = Path(raw)
    if not p.is_absolute():
        project_root = Path(__file__).parent.parent
        p = project_root / p
    return p
```

- [ ] **Step 5: Run dictionary tests**

```bash
pytest tests/test_config_manager.py -v -k "dictionary"
```
Expected: all PASSED.

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all PASSED.

- [ ] **Step 7: Commit**

```bash
git add manager/config_manager.py tests/test_config_manager.py
git commit -m "feat: add dictionary_file serialization and get_dictionary_path to config_manager"
```

---

## Task 7: manager/server.py — Dictionary API Endpoints

**Files:**
- Modify: `manager/server.py`

- [ ] **Step 1: Update `SAMPLE_ENTRY` in `tests/test_api.py` BEFORE adding `dictionary_file` to `ServerEntry`**

> ⚠️ Do this step first. Adding `dictionary_file` to `ServerEntry` will cause `model_dump()` to include it, breaking `test_post_server_success` and `test_put_server_success` which assert against `SAMPLE_ENTRY`. Update the dict now so those tests keep passing.

In `tests/test_api.py`, update `SAMPLE_ENTRY` to add `"dictionary_file": ""`:

```python
SAMPLE_ENTRY = {
    "name": "db-test",
    "connection_string": "Driver={ODBC Driver 17 for SQL Server};Server=srv1;Database=DB;Trusted_Connection=yes",
    "max_rows": 100,
    "query_timeout": 30,
    "pool_size": 5,
    "pool_timeout": 30,
    "allowed_schemas": "dbo",
    "blacklist_tables": "",
    "log_level": "INFO",
    "dictionary_file": "",
}
```

Run the full test suite to confirm existing tests still pass:

```bash
pytest tests/test_api.py -v
```
Expected: all PASSED (the `dictionary_file` key just gets ignored by `ServerEntry` until the model is updated in Step 4).

- [ ] **Step 2: Write failing tests for the new dictionary endpoints**

Add these tests to `tests/test_api.py`:

```python
# ── Dictionary endpoints ────────────────────────────────────────────────────

def test_get_dictionary_returns_content(tmp_path):
    dict_path = tmp_path / "dict.md"
    dict_path.write_text("# Dizionario", encoding="utf-8")
    with patch("manager.server.config_manager.get_dictionary_path", return_value=dict_path):
        response = client.get("/api/dictionary/db-test")
    assert response.status_code == 200
    assert response.json()["content"] == "# Dizionario"


def test_get_dictionary_returns_empty_when_file_missing(tmp_path):
    dict_path = tmp_path / "nonexistent.md"
    with patch("manager.server.config_manager.get_dictionary_path", return_value=dict_path):
        response = client.get("/api/dictionary/db-test")
    assert response.status_code == 200
    assert response.json()["content"] == ""


def test_get_dictionary_404_for_unknown_server():
    with patch("manager.server.config_manager.get_dictionary_path", side_effect=KeyError("not found")):
        response = client.get("/api/dictionary/db-unknown")
    assert response.status_code == 404


def test_post_dictionary_saves_content(tmp_path):
    dict_path = tmp_path / "dict.md"
    with patch("manager.server.config_manager.get_dictionary_path", return_value=dict_path):
        response = client.post("/api/dictionary/db-test", json={"content": "# New content"})
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert dict_path.read_text(encoding="utf-8") == "# New content"


def test_post_dictionary_404_for_unknown_server():
    with patch("manager.server.config_manager.get_dictionary_path", side_effect=KeyError("not found")):
        response = client.post("/api/dictionary/db-test", json={"content": "x"})
    assert response.status_code == 404
```

Also update `SAMPLE_ENTRY` in `test_api.py` to include `"dictionary_file": ""` (required because `ServerEntry` will gain this field with a default, and `model_dump()` will include it):

```python
SAMPLE_ENTRY = {
    "name": "db-test",
    "connection_string": "Driver={ODBC Driver 17 for SQL Server};Server=srv1;Database=DB;Trusted_Connection=yes",
    "max_rows": 100,
    "query_timeout": 30,
    "pool_size": 5,
    "pool_timeout": 30,
    "allowed_schemas": "dbo",
    "blacklist_tables": "",
    "log_level": "INFO",
    "dictionary_file": "",
}
```

- [ ] **Step 3: Run tests to verify dictionary tests fail**

```bash
pytest tests/test_api.py -v -k "dictionary"
```
Expected: FAILED (endpoints don't exist yet). The pre-existing tests should still PASS.

- [ ] **Step 4: Add `import os` to manager/server.py**

Add `import os` to the imports block at the top of `manager/server.py`.

- [ ] **Step 5: Add `dictionary_file` to `ServerEntry`**

In the `ServerEntry` Pydantic model, add:

```python
dictionary_file: Optional[str] = ""
```

- [ ] **Step 6: Add `DictionaryContent` model**

After `TestRequest`, add:

```python
class DictionaryContent(BaseModel):
    content: str
```

- [ ] **Step 7: Add GET and POST endpoints**

After the `POST /api/test` endpoint, add:

```python
@app.get("/api/dictionary/{server_name}")
def get_dictionary(server_name: str):
    try:
        path = config_manager.get_dictionary_path(server_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if not path.exists():
        return {"content": ""}
    return {"content": path.read_text(encoding="utf-8")}


@app.post("/api/dictionary/{server_name}")
def save_dictionary(server_name: str, body: DictionaryContent):
    try:
        path = config_manager.get_dictionary_path(server_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(body.content, encoding="utf-8")
        os.replace(tmp, path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"ok": True}
```

- [ ] **Step 8: Update `register-claude-code` to include `dictionary_file`**

In the `register_claude_code` function, add `("dictionary_file", "--dictionary-file")` to the field/flag loop:

```python
for field, flag in (("max_rows", "--max-rows"), ("query_timeout", "--query-timeout"),
                    ("pool_size", "--pool-size"), ("pool_timeout", "--pool-timeout"),
                    ("allowed_schemas", "--allowed-schemas"),
                    ("blacklist_tables", "--blacklist-tables"),
                    ("log_level", "--log-level"),
                    ("dictionary_file", "--dictionary-file")):
```

- [ ] **Step 9: Run all tests**

```bash
pytest tests/ -v
```
Expected: all PASSED.

- [ ] **Step 10: Commit**

```bash
git add manager/server.py tests/test_api.py
git commit -m "feat: add GET/POST /api/dictionary endpoints and dictionary_file to ServerEntry"
```

---

## Task 8: index.html — 📖 Button, Modal Editor, Form Field

**Files:**
- Modify: `manager/static/index.html`

- [ ] **Step 1: Add modal CSS**

Inside the `<style>` block, after `.btn-sm.green:hover { background: #f0fdf4; }`, add:

```css
/* Dictionary modal */
.modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.45); z-index: 100; align-items: center; justify-content: center; }
.modal-overlay.visible { display: flex; }
.modal-box { background: #fff; border-radius: 14px; padding: 28px; width: min(700px, 92vw); max-height: 88vh; display: flex; flex-direction: column; gap: 14px; box-shadow: 0 20px 60px rgba(0,0,0,0.18); }
.modal-title { font-size: 1rem; font-weight: 700; margin-bottom: 2px; }
.modal-hint { font-size: 0.75rem; color: #94a3b8; }
.modal-textarea { flex: 1; width: 100%; min-height: 360px; font-family: 'Courier New', monospace; font-size: 0.8rem; line-height: 1.5; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; resize: vertical; }
.modal-textarea:focus { outline: none; border-color: #6c63ff; box-shadow: 0 0 0 3px #6c63ff22; }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; align-items: center; }
```

- [ ] **Step 2: Add modal HTML**

Before the closing `</div>` of `<div class="wrap">` (i.e., before the `</div>` on line ~119), add:

```html
<!-- Dictionary Modal -->
<div class="modal-overlay" id="dict-modal" onclick="if(event.target===this)closeDictionary()">
  <div class="modal-box">
    <div>
      <div class="modal-title" id="dict-modal-title">Dizionario Semantico</div>
      <div class="modal-hint">Aggiornato automaticamente da Claude. Puoi modificarlo manualmente o copiare sezioni da altri dizionari.</div>
    </div>
    <textarea class="modal-textarea" id="dict-textarea" placeholder="Il dizionario è vuoto. Claude lo popolerà automaticamente durante le conversazioni."></textarea>
    <div class="modal-footer">
      <span class="test-result" id="dict-save-result" style="margin-right:auto"></span>
      <button class="btn-cancel" onclick="closeDictionary()">Chiudi</button>
      <button class="btn-save" onclick="saveDictionary()">Salva Modifiche</button>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add 📖 button to `renderList()`**

In `renderList()`, find this exact line (line 159 in the current file):

```
          <button class="btn-sm green" onclick="registerClaudeCode(${i})" title="Registra su Claude Code">CC</button>
```

Insert a new line immediately after it (keep the same 10-space indentation):

```
          <button class="btn-sm" onclick="openDictionary(${i})" title="Dizionario semantico">📖</button>
```

So the three lines in sequence become:
```
          <button class="btn-sm green" onclick="registerClaudeCode(${i})" title="Registra su Claude Code">CC</button>
          <button class="btn-sm" onclick="openDictionary(${i})" title="Dizionario semantico">📖</button>
          <button class="btn-sm" onclick="editCard(${i})">✏️</button>
```

- [ ] **Step 4: Add `dictionary_file` field to the form**

In the form grid, after the `Pool Timeout` field group (before the closing `</div>` of `.form-grid`), add:

```html
<div class="form-group form-full">
  <label>File Dizionario <span style="font-weight:400;color:#94a3b8">(opzionale)</span></label>
  <input type="text" id="f-dictionary-file" placeholder="semantic_dictionary.md">
  <small style="color:#94a3b8;font-size:0.72rem;display:block;margin-top:3px">Path dove Claude salva la conoscenza semantica. Lascia vuoto per il default.</small>
</div>
```

- [ ] **Step 5: Update `editCard()` to populate the field**

In `editCard(i)`, after `document.getElementById('f-pool-timeout').value = ...`, add:

```javascript
document.getElementById('f-dictionary-file').value = s.dictionary_file || '';
```

- [ ] **Step 6: Update `openForm()` to clear the field**

In the `forEach` clearing all form fields, add `'f-dictionary-file'` to the array:

```javascript
['f-conn','f-max-rows','f-schemas','f-blacklist','f-query-timeout','f-pool-size','f-pool-timeout','f-dictionary-file']
  .forEach(id => document.getElementById(id).value = '');
```

- [ ] **Step 7: Update `saveForm()` to send `dictionary_file`**

In the `body` object in `saveForm()`, after `log_level: 'INFO'`, add:

```javascript
dictionary_file: document.getElementById('f-dictionary-file').value.trim(),
```

- [ ] **Step 8: Add dictionary JS functions**

Before `loadServers();` at the bottom of the `<script>` block, add:

```javascript
let dictServerName = null;

async function openDictionary(i) {
  if (!servers[i]) return;
  dictServerName = servers[i].name;
  document.getElementById('dict-modal-title').textContent = `Dizionario Semantico — ${esc(dictServerName)}`;
  document.getElementById('dict-textarea').value = '';
  document.getElementById('dict-save-result').textContent = '';
  document.getElementById('dict-save-result').className = 'test-result';
  document.getElementById('dict-modal').classList.add('visible');
  try {
    const res = await fetch(`/api/dictionary/${encodeURIComponent(dictServerName)}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    document.getElementById('dict-textarea').value = data.content;
  } catch (e) {
    document.getElementById('dict-save-result').textContent = '❌ Errore caricamento: ' + e.message;
    document.getElementById('dict-save-result').className = 'test-result fail';
  }
}

function closeDictionary() {
  document.getElementById('dict-modal').classList.remove('visible');
  dictServerName = null;
}

async function saveDictionary() {
  if (!dictServerName) return;
  const content = document.getElementById('dict-textarea').value;
  const resultEl = document.getElementById('dict-save-result');
  resultEl.textContent = '⏳ Salvataggio...';
  resultEl.className = 'test-result';
  try {
    const res = await fetch(`/api/dictionary/${encodeURIComponent(dictServerName)}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({content}),
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Errore');
    resultEl.textContent = '✅ Salvato';
    resultEl.className = 'test-result ok';
  } catch (e) {
    resultEl.textContent = '❌ ' + e.message;
    resultEl.className = 'test-result fail';
  }
}
```

- [ ] **Step 9: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all PASSED.

- [ ] **Step 10: Commit**

```bash
git add manager/static/index.html
git commit -m "feat: add dictionary modal UI with 📖 button and form field"
```

---

## Final Verification

- [ ] **Step 1: Run complete test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: all tests pass, no regressions.

- [ ] **Step 2: Commit summary**

```bash
git log --oneline -8
```
Expected: 7 new commits visible.
