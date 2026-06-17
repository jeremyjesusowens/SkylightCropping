#!/usr/bin/env bash
# Build the macOS binary. Equivalent to build.bat on Windows.
set -e
pip install -r requirements.txt pyinstaller
git rev-parse --short HEAD > build_info.txt
pyinstaller --onefile --windowed \
  --collect-data customtkinter \
  --add-data "assets:assets" \
  --add-data "build_info.txt:." \
  --name SkylightCropping app.py
echo "Binary at: dist/SkylightCropping"
