@echo off
echo Starting Majool Inventory Backend...
cd /d %~dp0
call inventory_backend\env\Scripts\activate.bat
python -m inventory_backend.main
pause