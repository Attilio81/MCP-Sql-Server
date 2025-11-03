"""
Script di test per verificare la connessione al database SQL Server
Esegui questo script prima di configurare Claude Desktop per verificare che tutto funzioni
"""

import os
import sys
import io
from dotenv import load_dotenv

# Configure UTF-8 output for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Load environment variables
load_dotenv()

def test_pyodbc_installed():
    """Test 1: Verifica che pyodbc sia installato"""
    print("Test 1: Verifica installazione pyodbc...")
    try:
        import pyodbc
        print(f"✓ pyodbc versione {pyodbc.version} installato correttamente")
        return True
    except ImportError as e:
        print(f"✗ pyodbc non installato: {e}")
        print("  Esegui: pip install pyodbc")
        return False


def test_odbc_drivers():
    """Test 2: Elenca driver ODBC disponibili"""
    print("\nTest 2: Driver ODBC disponibili...")
    try:
        import pyodbc
        drivers = pyodbc.drivers()
        if not drivers:
            print("✗ Nessun driver ODBC trovato")
            print("  Installa ODBC Driver for SQL Server:")
            print("  https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server")
            return False

        print("✓ Driver disponibili:")
        for driver in drivers:
            print(f"  - {driver}")

        # Check for SQL Server drivers
        sql_drivers = [d for d in drivers if "SQL Server" in d]
        if sql_drivers:
            print(f"\n✓ Driver SQL Server trovati: {len(sql_drivers)}")
            return True
        else:
            print("\n⚠ Nessun driver SQL Server trovato")
            return False
    except Exception as e:
        print(f"✗ Errore verifica driver: {e}")
        return False


def test_connection_string():
    """Test 3: Verifica connection string configurata"""
    print("\nTest 3: Verifica configurazione...")
    conn_str = os.getenv("SQL_CONNECTION_STRING")

    if not conn_str:
        print("✗ SQL_CONNECTION_STRING non configurata")
        print("  Crea file .env con la tua connection string")
        print("  Copia .env.example come template")
        return False

    print(f"✓ Connection string configurata")
    # Mask password in output
    safe_str = conn_str
    if "PWD=" in safe_str:
        import re
        safe_str = re.sub(r'PWD=([^;]+)', 'PWD=****', safe_str)
    print(f"  {safe_str}")
    return True


def test_database_connection():
    """Test 4: Prova connessione al database"""
    print("\nTest 4: Test connessione database...")

    conn_str = os.getenv("SQL_CONNECTION_STRING")
    if not conn_str:
        print("✗ Salta test (connection string non configurata)")
        return False

    try:
        import pyodbc
        timeout = int(os.getenv("QUERY_TIMEOUT", "30"))

        print(f"  Tentativo connessione (timeout={timeout}s)...")
        conn = pyodbc.connect(conn_str, timeout=timeout)

        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]

        print(f"✓ Connessione riuscita!")
        print(f"  SQL Server versione:")
        # Print first line of version
        print(f"  {version.split(chr(10))[0]}")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"✗ Connessione fallita: {e}")
        print("\n  Verifica:")
        print("  1. Il server SQL Server è avviato")
        print("  2. Le credenziali sono corrette")
        print("  3. Il firewall permette la connessione")
        print("  4. Il nome del database è corretto")
        return False


def test_basic_query():
    """Test 5: Esegui query di base"""
    print("\nTest 5: Test query di base...")

    conn_str = os.getenv("SQL_CONNECTION_STRING")
    if not conn_str:
        print("✗ Salta test (connection string non configurata)")
        return False

    try:
        import pyodbc
        conn = pyodbc.connect(conn_str, timeout=int(os.getenv("QUERY_TIMEOUT", "30")))
        cursor = conn.cursor()

        # List tables
        cursor.execute("""
            SELECT COUNT(*) as TableCount
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
        """)
        count = cursor.fetchone()[0]

        print(f"✓ Query eseguita con successo")
        print(f"  Tabelle trovate: {count}")

        if count > 0:
            # Show first 5 tables
            cursor.execute("""
                SELECT TOP 5 TABLE_SCHEMA, TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_SCHEMA, TABLE_NAME
            """)
            print("  Esempio tabelle:")
            for schema, table in cursor.fetchall():
                print(f"    - {schema}.{table}")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"✗ Query fallita: {e}")
        return False


def test_mcp_package():
    """Test 6: Verifica installazione package MCP"""
    print("\nTest 6: Verifica package MCP...")
    try:
        import mcp
        print(f"✓ Package 'mcp' installato")

        # Try importing our server
        try:
            from mcp_sqlserver import server
            print(f"✓ Module 'mcp_sqlserver.server' importato correttamente")
            return True
        except ImportError as e:
            print(f"⚠ mcp_sqlserver.server non trovato: {e}")
            print("  Esegui: pip install -e .")
            return False

    except ImportError as e:
        print(f"✗ Package 'mcp' non installato: {e}")
        print("  Esegui: pip install mcp")
        return False


def main():
    """Esegui tutti i test"""
    print("=" * 70)
    print("TEST CONNESSIONE MCP SQL SERVER")
    print("=" * 70)

    results = []

    # Run all tests
    results.append(("pyodbc installato", test_pyodbc_installed()))
    results.append(("Driver ODBC", test_odbc_drivers()))
    results.append(("Connection string", test_connection_string()))
    results.append(("Connessione DB", test_database_connection()))
    results.append(("Query base", test_basic_query()))
    results.append(("Package MCP", test_mcp_package()))

    # Summary
    print("\n" + "=" * 70)
    print("RIEPILOGO TEST")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print("\n" + "=" * 70)
    print(f"Risultato: {passed}/{total} test superati")

    if passed == total:
        print("\n🎉 Tutti i test superati! Il server MCP è pronto per essere configurato in Claude Desktop.")
        print("\nProssimi passi:")
        print("1. Copia claude_desktop_config.example.json")
        print("2. Aggiornalo con le tue credenziali")
        print("3. Aggiungi la configurazione a Claude Desktop")
        print("4. Riavvia Claude Desktop")
    else:
        print("\n⚠ Alcuni test falliti. Risolvi i problemi prima di configurare Claude Desktop.")
        sys.exit(1)

    print("=" * 70)


if __name__ == "__main__":
    main()
