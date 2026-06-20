#!/usr/bin/env bash
# Build the macOS binary. Equivalent to build.bat on Windows.
set -e
if command -v uv >/dev/null 2>&1; then
  uv pip install --system -r requirements.txt pyinstaller
else
  pip install -r requirements.txt pyinstaller
fi
git rev-parse --short HEAD > build_info.txt
pyinstaller --onefile --windowed \
  --collect-data customtkinter \
  --add-data "assets:assets" \
  --add-data "build_info.txt:." \
  --name SkylightCropping app.py
echo "Binary at: dist/SkylightCropping"
