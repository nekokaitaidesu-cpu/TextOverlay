@echo off
echo EXEをビルドします...
pip install -r requirements.txt
pyinstaller --onefile --windowed --name TextOverlay main.py
echo.
echo ビルド完了！ dist\TextOverlay.exe を実行してください。
pause
