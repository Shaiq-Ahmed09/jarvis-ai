# J.A.R.V.I.S. Windows Startup Shortcut Installer / Uninstaller
param(
    [switch]$Uninstall = $false
)

$RootDir = $PSScriptRoot
$StartupDir = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupDir "JARVIS Desktop.lnk"

if ($Uninstall) {
    if (Test-Path $ShortcutPath) {
        Remove-Item $ShortcutPath -Force
        Write-Host "✅ J.A.R.V.I.S. Startup shortcut removed successfully." -ForegroundColor Green
    } else {
        Write-Host "ℹ️ Startup shortcut was not found." -ForegroundColor Yellow
    }
    return
}

$VbsPath = Join-Path $RootDir "start_jarvis_desktop.vbs"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = "`"$VbsPath`""
$Shortcut.WorkingDirectory = $RootDir
$Shortcut.Description = "J.A.R.V.I.S. Desktop AI Bubble & Background System"
$Shortcut.WindowStyle = 7 # Minimized/Hidden
$Shortcut.Save()

Write-Host "✅ J.A.R.V.I.S. Startup shortcut installed successfully!" -ForegroundColor Green
Write-Host "   Shortcut: $ShortcutPath" -ForegroundColor Cyan
Write-Host "   J.A.R.V.I.S. will now start silently upon Windows login." -ForegroundColor Gray
