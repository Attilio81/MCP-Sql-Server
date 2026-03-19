# -*- coding: utf-8 -*-
"""
Connection pool management for MCP SQL Server.
Thread-safe connection pool with automatic reconnection.
"""

import logging
from contextlib import contextmanager
from queue import Queue, Empty
import pyodbc

logger = logging.getLogger(__name__)


class ConnectionPool:
    """Thread-safe connection pool for SQL Server"""

    def __init__(self, connection_string: str, pool_size: int = 5, timeout: int = 30):
        if not connection_string:
            raise ValueError("SQL_CONNECTION_STRING non configurata")

        self.connection_string = connection_string
        self.pool_size = pool_size
        self.timeout = timeout
        self.pool: Queue = Queue(maxsize=pool_size)

        # Initialize pool
        logger.info(f"Inizializzazione pool connessioni (size={pool_size})")
        for _ in range(pool_size):
            try:
                conn = pyodbc.connect(connection_string, timeout=timeout)
                self.pool.put(conn)
            except Exception as e:
                logger.error(f"Errore creazione connessione nel pool: {e}")
                raise

    @contextmanager
    def get_connection(self):
        """Get connection from pool with automatic return"""
        conn = None
        try:
            conn = self.pool.get(timeout=self.timeout)
            # Verify connection is alive
            try:
                conn.execute("SELECT 1").fetchone()
            except Exception as e:
                # Connection is dead, create new one
                logger.warning("Connessione morta nel pool, creazione nuova connessione: %s", e)
                try:
                    conn.close()
                except Exception as close_err:
                    logger.debug("Errore chiusura connessione morta: %s", close_err)
                conn = pyodbc.connect(self.connection_string, timeout=self.timeout)

            yield conn
        except Empty:
            logger.error("Timeout acquisizione connessione dal pool")
            raise TimeoutError("Pool connessioni esaurito")
        finally:
            if conn:
                try:
                    # Rollback any pending transactions
                    conn.rollback()
                    self.pool.put(conn)
                except Exception as e:
                    logger.warning("Connessione rotta durante il rilascio nel pool: %s", e)
                    # Connection is broken, create new one for pool
                    try:
                        conn.close()
                    except Exception as close_err:
                        logger.debug("Errore chiusura connessione rotta: %s", close_err)
                    try:
                        new_conn = pyodbc.connect(self.connection_string, timeout=self.timeout)
                        self.pool.put(new_conn)
                    except Exception as reconn_err:
                        logger.error(f"Impossibile ripristinare connessione nel pool: {reconn_err}")

    def close_all(self):
        """Close all connections in pool"""
        logger.info("Chiusura pool connessioni")
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                conn.close()
            except Exception as e:
                logger.debug("Errore chiusura connessione durante close_all: %s", e)
