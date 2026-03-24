# -*- coding: utf-8 -*-
"""Tool handler: update_dictionary — saves semantic mappings to the dictionary file."""

import re
import logging
from pathlib import Path

from mcp.types import TextContent

from mcp_sqlserver import config
from mcp_sqlserver.pool import ConnectionPool

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


async def handle_update_dictionary(pool: ConnectionPool, arguments: dict) -> list[TextContent]:
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
    try:
        dict_path.write_text(updated, encoding="utf-8")
    except OSError as e:
        return [TextContent(type="text", text=f"❌ Errore scrittura dizionario: {e}")]

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
