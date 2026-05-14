@echo off
echo Installing PyInstaller...
pip install pyinstaller

echo Building the application with PyInstaller...
pyinstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --hidden-import=yt_dlp ^
  --name "AudioBookConverter" ^
  --exclude-module=pandas ^
  --exclude-module=numpy ^
  --exclude-module=scipy ^
  --exclude-module=matplotlib ^
  main.py

echo Build complete! Your AudioBookConverter.exe will be inside the "dist" folder.
pause