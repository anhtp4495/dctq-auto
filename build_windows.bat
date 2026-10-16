@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Khong tim thay .venv. Hay tao moi truong va cai requirements truoc.
    echo   py -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo [1/3] Cai dat PyInstaller...
".venv\Scripts\python.exe" -m pip install --upgrade pyinstaller
if errorlevel 1 goto :error

echo [2/3] Xoa ban build cu...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/3] Dong goi DCTQ-Auto.exe...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name DCTQ-Auto --collect-all PySide6 --collect-all cv2 dctq_auto\__main__.py
if errorlevel 1 goto :error

echo.
echo Build thanh cong: dist\DCTQ-Auto.exe
echo Luu y: che do ADB van can emulator va ADB executable kha dung tren may.
pause
exit /b 0

:error
echo.
echo [ERROR] Build that bai. Kiem tra thong bao loi o phia tren.
pause
exit /b 1
