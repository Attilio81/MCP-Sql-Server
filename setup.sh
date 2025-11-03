#!/bin/bash
# Setup script per MCP SQL Server su Linux/macOS

set -e

echo "========================================"
echo "MCP SQL Server - Setup"
echo "========================================"
echo ""

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 non trovato!"
    echo "Installa Python 3.10+ dal package manager del tuo sistema"
    exit 1
fi

echo "[1/5] Python trovato"
python3 --version

# Create virtual environment (optional but recommended)
echo ""
echo "[2/5] Vuoi creare un virtual environment? (raccomandato)"
read -p "Crea venv? (s/n): " CREATE_VENV
if [[ "$CREATE_VENV" =~ ^[sS]$ ]]; then
    echo "Creazione virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Virtual environment attivato"
else
    echo "Salta creazione virtual environment"
fi

# Install package
echo ""
echo "[3/5] Installazione package in modalita development..."
pip install -e .

# Setup .env file
echo ""
echo "[4/5] Configurazione file .env..."
if [ ! -f .env ]; then
    echo "Copia .env.example a .env..."
    cp .env.example .env
    echo ""
    echo "IMPORTANTE: Edita il file .env con le tue credenziali SQL Server!"
    echo ""
    read -p "Vuoi aprire .env ora? (s/n): " EDIT_ENV
    if [[ "$EDIT_ENV" =~ ^[sS]$ ]]; then
        ${EDITOR:-nano} .env
    fi
else
    echo "File .env gia esistente, non sovrascritto"
fi

# Run connection test
echo ""
echo "[5/5] Test connessione al database..."
echo ""
read -p "Vuoi testare la connessione ora? (s/n): " RUN_TEST
if [[ "$RUN_TEST" =~ ^[sS]$ ]]; then
    python3 test_connection.py
fi

echo ""
echo "========================================"
echo "Setup completato!"
echo "========================================"
echo ""
echo "Prossimi passi:"
echo "1. Configura il file .env con le tue credenziali"
echo "2. Esegui: python3 test_connection.py"
echo "3. Configura Claude Desktop con claude_desktop_config.example.json"
echo "4. Riavvia Claude Desktop"
echo ""
