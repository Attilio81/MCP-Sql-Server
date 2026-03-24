# -*- coding: utf-8 -*-
"""Unit tests for dictionary tool — no database required."""
import asyncio
from pathlib import Path
from unittest.mock import patch

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
            return await handle_update_dictionary(None, arguments)
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
