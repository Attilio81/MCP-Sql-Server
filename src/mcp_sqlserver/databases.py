# -*- coding: utf-8 -*-
"""
Multi-database registry for MCP SQL Server.

One server process can serve many named databases, each with its own
connection pool, limits, and security rules. Databases are defined in a
JSON file passed via --databases; the legacy single-database mode
(--connection-string) registers one database under the name "default".
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from mcp_sqlserver import config
from mcp_sqlserver.pool import ConnectionPool

logger = logging.getLogger(__name__)

# Where dictionaries default to in multi-db mode: next to databases.json
_INT_FIELDS = ("max_rows", "query_timeout", "pool_size", "pool_timeout")


@dataclass
class Database:
    """A named database with its own settings and lazily-created pool."""

    name: str
    connection_string: str
    max_rows: int = 100
    query_timeout: int = 30
    pool_size: int = 5
    pool_timeout: int = 30
    blacklist_tables: list[str] = field(default_factory=list)
    allowed_schemas: list[str] = field(default_factory=list)
    dictionary_file: str = "semantic_dictionary.md"
    _pool: Optional[ConnectionPool] = field(default=None, repr=False, compare=False)
    _pool_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    @property
    def pool(self) -> ConnectionPool:
        """Connection pool, created on first use (handlers run in worker threads)."""
        with self._pool_lock:
            if self._pool is None:
                logger.info("Creazione pool per database '%s'", self.name)
                self._pool = ConnectionPool(self.connection_string, self.pool_size, self.pool_timeout)
            return self._pool

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close_all()
            self._pool = None


DATABASES: dict[str, Database] = {}


def _parse_list(value) -> list[str]:
    """Accept both JSON arrays and comma-separated strings."""
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def load_databases() -> None:
    """Populate the registry from --databases JSON or legacy single-db config."""
    DATABASES.clear()

    if config.DATABASES_FILE:
        path = Path(config.DATABASES_FILE)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data:
            raise ValueError(f"File databases vuoto o non valido: {path}")
        for name, entry in data.items():
            conn_str = (entry.get("connection_string") or "").strip()
            if not conn_str:
                raise ValueError(f"Database '{name}': connection_string mancante")
            kwargs = {}
            for f in _INT_FIELDS:
                if entry.get(f) is not None:
                    kwargs[f] = int(entry[f])
            dict_file = entry.get("dictionary_file") or str(path.parent / f"{name}_dictionary.md")
            DATABASES[name] = Database(
                name=name,
                connection_string=conn_str,
                blacklist_tables=_parse_list(entry.get("blacklist_tables")),
                allowed_schemas=[s.lower() for s in _parse_list(entry.get("allowed_schemas"))],
                dictionary_file=dict_file,
                **kwargs,
            )
        logger.info("Registrati %d database: %s", len(DATABASES), ", ".join(sorted(DATABASES)))
    elif config.CONNECTION_STRING:
        # Legacy single-database mode
        DATABASES["default"] = Database(
            name="default",
            connection_string=config.CONNECTION_STRING,
            max_rows=config.MAX_ROWS,
            query_timeout=config.QUERY_TIMEOUT,
            pool_size=config.POOL_SIZE,
            pool_timeout=config.POOL_TIMEOUT,
            blacklist_tables=config.BLACKLIST_TABLES,
            allowed_schemas=config.ALLOWED_SCHEMAS,
            dictionary_file=config.DICTIONARY_FILE,
        )


def is_multi() -> bool:
    """True when more than one database is configured (database param required)."""
    return len(DATABASES) > 1


def get_database(name: Optional[str] = None) -> Database:
    """Resolve a database by name. Raises KeyError with a helpful message."""
    if not DATABASES:
        raise KeyError("Nessun database configurato")
    if name:
        if name not in DATABASES:
            raise KeyError(
                f"Database '{name}' non configurato. Disponibili: {', '.join(sorted(DATABASES))}"
            )
        return DATABASES[name]
    if len(DATABASES) == 1:
        return next(iter(DATABASES.values()))
    raise KeyError(
        f"Parametro 'database' obbligatorio. Disponibili: {', '.join(sorted(DATABASES))}"
    )


def close_all() -> None:
    for db in DATABASES.values():
        db.close()
