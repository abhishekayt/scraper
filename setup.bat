@echo off
setlocal

echo ================================================
echo  UTIITSL PAN Center Scraper - Setup
echo ================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found on this system, or is not on PATH.
    echo.
    echo Install Python 3.8 or newer from https://python.org/downloads
    echo During install, make sure "Add python.exe to PATH" is checked.
    echo.
    pause
    exit /b 1
)

echo Found Python:
python --version
echo.

echo Installing required Python packages (playwright, beautifulsoup4, pandas, openpyxl)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: pip install failed. See the messages above for details.
    pause
    exit /b 1
)
echo.

echo Installing Chromium browser for Playwright (this may take a minute)...
python -m playwright install chromium
if errorlevel 1 (
    echo.
    echo ERROR: playwright install failed. See the messages above for details.
    pause
    exit /b 1
)
echo.

echo ================================================
echo  Setup complete!
echo ================================================
echo.
echo To start scraping, open a terminal in this folder and run:
echo.
echo     python run_all.py
echo.
echo A browser window will open for you to solve each CAPTCHA yourself.
echo See README.md for full usage details.
echo.
pause
