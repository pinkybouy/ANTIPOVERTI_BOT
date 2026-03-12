@echo off
title Binance Harvester Widget
echo =======================================================
echo Uruchamianie Mini Widgetu Binance...
echo Otworzy sie maly przezroczysty kafelek w rogu ekranu.
echo =======================================================

:: Uruchamianie pliku wykonywalnego
if exist "dist\TickWidget.exe" (
    cd dist
    start TickWidget.exe
) else (
    start pythonw widget.py
)
