@echo off
REM Setup script per MCP SQL Server su Windows

REM Spostati nella cartella del progetto (dove si trova questo bat)
cd /d "%~dp0"

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

REM Install package with manager dependencies
echo.
echo [3/5] Installazione package (incluso SQL MCP Manager)...
pip install -e ".[manager]"
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
    echo NOTA: Il file .env e opzionale - puoi usare il Manager per configurare
    echo       le connessioni direttamente in claude_desktop_config.json
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
echo 1. Avvia il Manager per configurare le connessioni:
echo      python -m manager.server
echo    Si apre automaticamente http://localhost:8090
echo    Aggiungi i tuoi SQL Server e testa le connessioni dalla UI.
echo.
echo 2. Riavvia Claude Desktop dopo aver salvato le connessioni.
echo.
set /p LAUNCH_MANAGER="Vuoi avviare il SQL MCP Manager ora? (s/n): "
if /i "%LAUNCH_MANAGER%"=="s" (
    echo Avvio SQL MCP Manager su http://localhost:8090 ...
    python -m manager.server
)
echo.
pause
