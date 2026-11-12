@echo off
REM Windows helper: checks Node, installs packages, builds the website. Run it by double-clicking or from Command Prompt.
REM It calls Vite through "node" directly, which avoids the common "permission denied / script disabled" problems with .cmd/.ps1 shims.
setlocal
cd /d "%~dp0"
echo === Node / npm versions ===
node --version || (echo Node.js is not installed. Install the LTS version from nodejs.org & exit /b 1)
call npm --version
for /f "tokens=1 delims=." %%v in ('node --version') do set NODEMAJOR=%%v
set NODEMAJOR=%NODEMAJOR:v=%
if %NODEMAJOR% LSS 18 (echo Node 18 or newer is required. Install the LTS version from nodejs.org & exit /b 1)
echo === Installing packages ===
call npm install
if errorlevel 1 (echo.& echo npm install FAILED. See BUILD-TROUBLESHOOTING.md and send the first error lines to Claude. & exit /b 1)
echo === Building ===
node node_modules\vite\bin\vite.js build
if errorlevel 1 (echo.& echo Build FAILED. See BUILD-TROUBLESHOOTING.md and send the first error lines to Claude. & exit /b 1)
echo.
echo BUILD OK. The website is in the "dist" folder.
