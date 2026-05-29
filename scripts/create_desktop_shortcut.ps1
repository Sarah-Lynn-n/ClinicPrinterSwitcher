$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ExePath = Join-Path $ProjectRoot "dist\ClinicPrinterSwitcher\ClinicPrinterSwitcher.exe"
$IconPath = Join-Path $ProjectRoot "assets\clinic_printer.ico"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Clinic Printer Switcher.lnk"

if (!(Test-Path $ExePath)) {
    Write-Host "EXE not found: $ExePath" -ForegroundColor Red
    Write-Host "Run .\build.ps1 first."
    exit 1
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $ExePath
$Shortcut.WorkingDirectory = Split-Path $ExePath
$Shortcut.IconLocation = $IconPath
$Shortcut.Description = "Clinic Printer Switcher"
$Shortcut.Save()

Write-Host "Desktop shortcut created:" -ForegroundColor Green
Write-Host $ShortcutPath
