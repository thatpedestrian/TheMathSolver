@echo off
echo Checking if XeLaTeX is already installed...
where xelatex >nul 2>&1
if %errorlevel% equ 0 (
    echo XeLaTeX is already installed.
    xelatex --version | findstr /i "xetex"
    goto :end
)

echo XeLaTeX not found. Installing MiKTeX via winget...
winget install MiKTeX.MiKTeX --accept-package-agreements --accept-source-agreements

if %errorlevel% neq 0 (
    echo.
    echo winget install failed. Please install MiKTeX manually:
    echo   https://miktex.org/download
    echo.
    echo Or install TeX Live:
    echo   https://www.tug.org/texlive/acquire-netinstall.html
    goto :end
)

echo.
echo MiKTeX installed successfully.
echo You may need to run: initexmf --update
echo.
echo Close and reopen your terminal, then verify with: xelatex --version

:end
pause
