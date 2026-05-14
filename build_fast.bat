@echo off
echo Installing PyInstaller...
pip install pyinstaller

echo Building the application with PyInstaller...
pyinstaller --noconfirm AudioBookConverter.spec

echo Build complete! Your AudioBookConverter.exe will be inside the "dist" folder.
pause