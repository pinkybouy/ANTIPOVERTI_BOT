@echo off
title ANTIPOVERTI HFT - Uruchamianie...
echo =======================================================
echo  ANTIPOVERTI HFT DASHBOARD
echo  Uruchamianie silnikow...
echo =======================================================
echo.

:: Ubij stare procesy na portach jesli istnieja
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5555 " ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8080 " ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1
timeout /t 1 >nul

:: [1] Uruchom Real Rust Engine (port 5555) w osobnym oknie
echo [1/2] Uruchamianie Real Rust Engine (Binance WS)...
start "ANTIPOVERTI - Real Engine" cmd /k "cd /d %~dp0 && cargo run --release"
timeout /t 5 >nul

:: [2] Uruchom Dashboard (port 8080) w osobnym oknie
echo [2/2] Uruchamianie Dashboard na porcie 8080...
start "ANTIPOVERTI - Dashboard" cmd /k "cd /d %~dp0ai_core && python dashboard.py"
timeout /t 3 >nul

:: [3] Otworz przegladarke
echo Otwieranie panelu w przegladarce...
start http://localhost:8080

echo.
echo =======================================================
echo  GOTOWE! Panel dostepny na: http://localhost:8080
echo  Zamknij okna "Mock Engine" i "Dashboard" aby zatrzymac.
echo =======================================================
timeout /t 5 >nul
exit
