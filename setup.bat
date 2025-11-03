@echo off
REM Setup script per MCP SQL Server su Windows

echo ========================================
echo MCP SQL Server - Setup
echo ========================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python non trovato!
    echo Installa Python 3.10+ da https://www.python.org/
    pause
    exit /b 1
)

echo [1/5] Python trovato
python --version

REM Create virtual environment (optional but recommended)
echo.
echo [2/5] Vuoi creare un virtual environment? (raccomandato)
set /p CREATE_VENV="Crea venv? (s/n): "
if /i "%CREATE_VENV%"=="s" (
    echo Creazione virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Virtual environment attivato
) else (
    echo Salta creazione virtual environment
)

REM Install package
echo.
echo [3/5] Installazione package in modalita development...
pip install -e .
if errorlevel 1 (
    echo [ERROR] Installazione fallita
    pause
    exit /b 1
)

REM Setup .env file
echo.
echo [4/5] Configurazione file .env...
if not exist .env (
    echo Copia .env.example a .env...
    copy .env.example .env
    echo.
    echo IMPORTANTE: Edita il file .env con le tue credenziali SQL Server!
    echo.
    set /p EDIT_ENV="Vuoi aprire .env ora? (s/n): "
    if /i "%EDIT_ENV%"=="s" (
        notepad .env
    )
) else (
    echo File .env gia esistente, non sovrascritto
)

REM Run connection test
echo.
echo [5/5] Test connessione al database...
echo.
set /p RUN_TEST="Vuoi testare la connessione ora? (s/n): "
if /i "%RUN_TEST%"=="s" (
    python test_connection.py
)

echo.
echo ========================================
echo Setup completato!
echo ========================================
echo.
echo Prossimi passi:
echo 1. Configura il file .env con le tue credenziali
echo 2. Esegui: python test_connection.py
echo 3. Configura Claude Desktop con claude_desktop_config.example.json
echo 4. Riavvia Claude Desktop
echo.
pause
