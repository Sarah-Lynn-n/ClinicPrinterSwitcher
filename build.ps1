$ErrorActionPreference = "Stop"

Write-Host "Installing dependencies..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host "Building ClinicPrinterSwitcher..." -ForegroundColor Cyan

pyinstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name ClinicPrinterSwitcher `
  --icon "assets\clinic_printer.ico" `
  --add-data "assets\clinic_printer.ico;assets" `
  main.py

Write-Host ""
Write-Host "Build complete:" -ForegroundColor Green
Write-Host "dist\ClinicPrinterSwitcher\ClinicPrinterSwitcher.exe"
Write-Host ""
Write-Host "To create desktop shortcut, run:" -ForegroundColor Yellow
Write-Host ".\scripts\create_desktop_shortcut.ps1"
