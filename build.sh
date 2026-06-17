#!/usr/bin/env bash
# Build the macOS binary. Equivalent to build.bat on Windows.
set -e
pip install -r requirements.txt pyinstaller
pyinstaller --onefile --windowed \
  --collect-data customtkinter \
  --add-data "assets:assets" \
  --name SkylightCropping app.py
echo "Binary at: dist/SkylightCropping"
