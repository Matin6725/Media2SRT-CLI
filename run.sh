#!/bin/bash

VENV_DIR=".venv"
LOCK_FILE="$VENV_DIR/.installing"

# Check if previous installation was interrupted or failed
if [ -f "$LOCK_FILE" ]; then
    echo "[WARNING] Previous installation was interrupted. Rebuilding environment..."
    rm -rf "$VENV_DIR"
fi

# Create virtual environment and install dependencies if not present
if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] Virtual environment (.venv) not found. Creating..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment."
        exit 1
    fi

    # Create temporary lock file
    touch "$LOCK_FILE"

    echo "[INFO] Installing required dependencies (google-genai)..."
    ./"$VENV_DIR"/bin/pip install google-genai
    if [ $? -ne 0 ]; then
        echo "[ERROR] Package installation failed. Please check your internet connection."
        exit 1
    fi

    # Remove lock file after successful installation
    rm -f "$LOCK_FILE"
    echo "[SUCCESS] Environment setup complete."
fi

# Launch the application
echo "[INFO] Launching Media2SRT-CLI..."
./"$VENV_DIR"/bin/python Media2SRT-CLI.py