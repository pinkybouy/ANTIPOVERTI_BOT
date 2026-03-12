@echo off
title Binance Tick Harvester - AKTYWNY SERWER
echo =======================================================
echo  Binance Tick Harvester
echo  BTC surowy serwer danych na zywo
echo =======================================================
echo.
echo  Panel sterowania: http://127.0.0.1:8000
echo  UWAGA: NIE ZAMYKAJ TEGO OKNA - to jest serwer!
echo  Bledy beda zapisywane tutaj i do: harvester_error.log
echo =======================================================
echo.

:: Otworzenie przegladarki po 3 sekundach
start /b cmd /c "ping localhost -n 3 > nul && start http://127.0.0.1:8000"

:: Sprawdz czy EXE istnieje - uzywaj pliku wykonywalnego jesli skompilowany
if exist "dist\TickHarvester.exe" (
    echo  Uruchamianie skompilowanej wersji EXE...
    cd dist
    TickHarvester.exe >> ..\harvester_error.log 2>&1
) else (
    echo  Uruchamianie przez Python...
    python main.py >> harvester_error.log 2>&1
)

:: Jesli tu dotarlismy, serwer sie zatrzymal (crash lub CTRL+C)
echo.
echo !! HARVESTER ZATRZYMAL SIE !!
echo    Sprawdz bledy w pliku: harvester_error.log
echo    lub przewin okno powyzej.
echo.
pause
