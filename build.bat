@echo off
echo =====================================================
echo  Skylight Cropping - Windows Build
echo =====================================================
echo.

echo Installing / updating dependencies...
pip install -r requirements.txt
pip install pyinstaller
echo.

echo Building executable...
pyinstaller ^
  --onefile ^
  --windowed ^
  --collect-data customtkinter ^
  --add-data "assets;assets" ^
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
pause
