@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto try_python
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto try_python
py -3 "%~dp0scripts\menu.py"
goto finished
:try_python
where python >nul 2>nul
if errorlevel 1 goto missing_python
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto missing_python
python "%~dp0scripts\menu.py"
goto finished
:missing_python
echo Python 3.10 or newer is required. Install it and enable Add Python to PATH.
echo https://www.python.org/downloads/
:finished
popd
pause
endlocal
