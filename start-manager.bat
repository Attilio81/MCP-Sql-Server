@echo off
REM Avvia il SQL MCP Manager - interfaccia web per gestire le connessioni SQL Server

REM Spostati nella cartella del progetto (dove si trova questo bat)
cd /d "%~dp0"

echo ========================================
echo SQL MCP Manager
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

REM Activate virtual environment if present
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM Check if manager is installed
python -c "import manager.server" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installazione dipendenze manager...
    pip install -e ".[manager]"
    if errorlevel 1 (
        echo [ERROR] Installazione fallita. Esegui prima setup.bat
        pause
        exit /b 1
    )
)

echo Avvio in corso...
echo Il browser si apre automaticamente su http://localhost:8090
echo Premi Ctrl+C per fermare il server.
echo.
python -m manager.server
