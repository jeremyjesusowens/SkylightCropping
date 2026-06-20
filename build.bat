@echo off
echo =====================================================
echo  Skylight Cropping - Windows Build
echo =====================================================
echo.

echo Installing / updating dependencies...
where uv >nul 2>nul
if %ERRORLEVEL% == 0 (
    uv pip install --system -r requirements.txt pyinstaller
) else (
    pip install -r requirements.txt
    pip install pyinstaller
)
echo.

echo Recording build version...
for /f %%i in ('git rev-parse --short HEAD') do echo %%i> build_info.txt
echo.

echo Building executable...
pyinstaller ^
  --onedir ^
  --windowed ^
  --collect-data customtkinter ^
  --add-data "assets;assets" ^
  --add-data "build_info.txt;." ^
  --icon "assets\icon.ico" ^
  --name "SkylightCropping" ^
  app.py

echo.
if exist "dist\SkylightCropping\SkylightCropping.exe" (
    echo =====================================================
    echo  Build successful!
    echo  Executable: dist\SkylightCropping\SkylightCropping.exe
    echo =====================================================
) else (
    echo =====================================================
    echo  Build FAILED. Check the output above for errors.
    echo =====================================================
)
echo.
if not defined CI pause
