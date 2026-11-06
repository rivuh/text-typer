@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt || goto :error
py -m PyInstaller --noconfirm --onefile --windowed --name TextTyper --icon icon.ico --add-data "icon.ico;." --collect-all customtkinter text_typer.py || goto :error
echo.
echo Built: %~dp0dist\TextTyper.exe
pause
exit /b 0

:error
echo Build failed.
pause
exit /b 1
