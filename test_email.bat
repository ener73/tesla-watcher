@echo off
cd /d "%~dp0"
echo Sende Test-E-Mail an aperathoner@gmail.com...
python tesla_watcher.py --test-email
pause
