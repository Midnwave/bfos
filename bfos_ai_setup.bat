@echo off
title BFOS AI Setup
color 0A

echo ============================================
echo        BFOS AI Setup Script
echo ============================================
echo.

:MENU
echo What do you want to do?
echo.
echo [1] Start Everything (Ollama + Bot)
echo [2] Start Ollama Only
echo [3] Stop Ollama
echo [4] Restart Ollama
echo [5] Test Cloud Models
echo [6] Check Ollama Status
echo [7] Start Bot Only
echo [8] Exit
echo.
set /p choice="Enter choice (1-8): "

if "%choice%"=="1" goto START_ALL
if "%choice%"=="2" goto START_OLLAMA
if "%choice%"=="3" goto STOP_OLLAMA
if "%choice%"=="4" goto RESTART_OLLAMA
if "%choice%"=="5" goto TEST_MODELS
if "%choice%"=="6" goto CHECK_STATUS
if "%choice%"=="7" goto START_BOT
if "%choice%"=="8" goto EXIT

echo Invalid choice, try again.
echo.
goto MENU

:START_ALL
echo.
echo [*] Starting Ollama and Bot...
call :ENSURE_OLLAMA
echo.
echo [*] Starting BFOS Bot...
cd /d "%~dp0"
start "BFOS Bot" cmd /k "python bot.py"
echo [+] Bot started in new window!
echo.
pause
goto MENU

:START_OLLAMA
echo.
call :ENSURE_OLLAMA
pause
goto MENU

:STOP_OLLAMA
echo.
echo [*] Stopping Ollama...
taskkill /F /IM ollama.exe >nul 2>&1
taskkill /F /IM ollama_llama_server.exe >nul 2>&1
echo [+] Ollama stopped!
echo.
pause
goto MENU

:RESTART_OLLAMA
echo.
echo [*] Restarting Ollama...
taskkill /F /IM ollama.exe >nul 2>&1
taskkill /F /IM ollama_llama_server.exe >nul 2>&1
timeout /t 2 >nul
call :ENSURE_OLLAMA
pause
goto MENU

:TEST_MODELS
echo.
echo [*] Testing cloud models...
echo.
echo Testing gemma3:27b-cloud (Vibe)...
echo (Type 'hi' and press Enter, then /bye to exit)
echo.
ollama run gemma3:27b-cloud
echo.
pause
goto MENU

:CHECK_STATUS
echo.
echo [*] Checking Ollama status...
echo.
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel%==0 (
    echo [+] Ollama is RUNNING on localhost:11434
    echo.
    echo Available models:
    ollama list
) else (
    echo [-] Ollama is NOT running
)
echo.
pause
goto MENU

:START_BOT
echo.
echo [*] Starting BFOS Bot...
cd /d "%~dp0"
start "BFOS Bot" cmd /k "python bot.py"
echo [+] Bot started in new window!
echo.
pause
goto MENU

:EXIT
echo.
echo Goodbye!
exit /b

REM ============================================
REM FUNCTIONS
REM ============================================

:ENSURE_OLLAMA
echo [*] Checking if Ollama is running...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel%==0 (
    echo [+] Ollama is already running!
    goto :EOF
)

echo [*] Ollama not running, starting it...

REM Kill any zombie processes
taskkill /F /IM ollama.exe >nul 2>&1
taskkill /F /IM ollama_llama_server.exe >nul 2>&1
timeout /t 1 >nul

REM Start Ollama in background
start /B "" ollama serve >nul 2>&1

REM Wait for it to be ready
echo [*] Waiting for Ollama to start...
set attempts=0

:WAIT_LOOP
timeout /t 1 >nul
set /a attempts+=1
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel%==0 (
    echo [+] Ollama started successfully!
    goto :EOF
)
if %attempts% lss 10 goto WAIT_LOOP

echo [-] ERROR: Ollama failed to start after 10 seconds
echo Try running 'ollama serve' manually to see the error
goto :EOF
