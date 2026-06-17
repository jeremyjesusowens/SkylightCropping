@echo off
echo =====================================================
echo  Skylight Cropping - Windows Build
echo =====================================================
echo.

echo Installing / updating dependencies...
pip install -r requirements.txt
pip install pyinstaller
echo.

echo Recording build version...
for /f %%i in ('git rev-parse --short HEAD') do echo %%i> build_info.txt
echo.

echo Building executable...
pyinstaller ^
  --onefile ^
  --windowed ^
  --collect-data customtkinter ^
  --add-data "assets;assets" ^
  --add-data "build_info.txt;." ^
  --icon "assets\icon.ico" ^
  --name "SkylightCropping" ^
  app.py

echo.
if exist "dist\SkylightCropping.exe" (
    echo =====================================================
    echo  Build successful!
    echo  Executable: dist\SkylightCropping.exe
    echo =====================================================
) else (
    echo =====================================================
    echo  Build FAILED. Check the output above for errors.
    echo =====================================================
)
echo.
if not defined CI pause
