@echo off
cd /d "%~dp0"
title Tesla Pronta Consegna Watcher (Model Y ^& Model 3)
echo Starte Tesla Inventory Watcher...
python tesla_watcher.py
pause
