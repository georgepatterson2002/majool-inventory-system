@echo off
title Launch PyQt5 Inventory App
color 0A
echo -------------------------------
echo Running PyQt5 Inventory App
echo -------------------------------

REM Activate virtual environment
call env\Scripts\activate.bat

REM Launch the PyQt app
python -m app.main
