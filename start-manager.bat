@echo off
REM Avvia il SQL MCP Manager - interfaccia web per gestire le connessioni SQL Server

REM Spostati nella cartella del progetto (dove si trova questo bat)
cd /d "%~dp0"

echo ========================================
echo SQL MCP Manager
echo ========================================
echo.
echo Cartella: %CD%
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python non trovato!
    echo Installa Python 3.10+ da https://www.python.org/
    pause
    exit /b 1
)

echo Python trovato:
python --version

REM Activate virtual environment if present
if exist venv\Scripts\activate.bat (
    echo Attivazione virtual environment...
    call venv\Scripts\activate.bat
)

REM Check if manager is installed
python -c "import manager.server" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installazione dipendenze manager...
    pip install -e ".[manager]"
    if errorlevel 1 (
        echo.
        echo [ERROR] Installazione fallita.
        echo Verifica di essere nella cartella giusta e di avere pip disponibile.
        pause
        exit /b 1
    )
)

echo.

REM Controlla se la porta 8090 e' gia' in uso
netstat -ano | findstr ":8090 " | findstr LISTENING >nul 2>&1
if not errorlevel 1 (
    echo Il manager e' gia' in esecuzione su http://localhost:8090
    echo Apertura browser...
    start http://localhost:8090
    timeout /t 2 >nul
    exit /b 0
)

echo Avvio in corso...
echo Il browser si apre automaticamente su http://localhost:8090
echo Premi Ctrl+C per fermare il server.
echo.
python -m manager.server
if errorlevel 1 (
    echo.
    echo [ERROR] Il server si e' fermato con un errore.
    pause
)
