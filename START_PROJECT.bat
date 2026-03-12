@echo off
title ANTIPOVERTI HFT Ecosystem Launcher
echo ======================================================
echo    ANTIPOVERTI HFT Ecosystem Launcher
echo ======================================================

echo [1/3] Uruchamianie Harvestera...
start "Harvester (Tick Scraper)" cmd /k "cd Harvester && python main.py"

timeout /t 2 /nobreak > nul

echo [2/3] Uruchamianie AI Core Engine...
start "Engine (AI Core)" cmd /k "cd Engine\ai_core && python main.py"

echo.
echo [3/3] cTrader Bot: Otwórz cTrader Automate i uruchom ANTIPOVERTI_BOT.
echo.
echo Wszystkie moduły Python zostały uruchomione w osobnych oknach.
echo Dashboardy:
echo   - Harvester: http://localhost:8000
echo   - Engine Dashboard: http://localhost:8080
echo.
pause
