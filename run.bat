@echo off
SET VENV_DIR=.venv
SET LOCK_FILE=%VENV_DIR%\.installing

:: Check if previous installation was interrupted or failed
IF EXIST "%LOCK_FILE%" (
    echo [WARNING] Previous installation was interrupted. Rebuilding environment...
    rmdir /s /q "%VENV_DIR%"
)

:: Create virtual environment and install dependencies if .venv doesn't exist
IF NOT EXIST "%VENV_DIR%" (
    echo [INFO] Virtual environment ^(.venv^) not found. Creating...
    python -m venv %VENV_DIR%
    IF %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b %ERRORLEVEL%
    )

    :: Create temporary lock file to track installation progress
    type nul > "%LOCK_FILE%"

    echo [INFO] Installing required dependencies ^(google-genai^)...
    %VENV_DIR%\Scripts\pip.exe install google-genai
    IF %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Package installation failed. Please check your internet connection.
        pause
        exit /b %ERRORLEVEL%
    )

    :: Remove lock file after successful installation
    del "%LOCK_FILE%"
    echo [SUCCESS] Environment setup complete.
)

echo [INFO] Launching Media2SRT-CLI...
%VENV_DIR%\Scripts\python.exe Media2SRT-CLI.py
pause