<#
============================================================================
 CAI Guard — one-shot build + install (no Inno Setup, no admin required)

 What it does, end to end:
   1. Verifies Python is available
   2. Builds CAIGuard.exe with PyInstaller in a private venv
   3. Installs it to %LOCALAPPDATA%\Programs\CAIGuard
   4. Creates Start Menu + Desktop shortcuts
   5. Registers it to start when you sign in
   6. Registers the CAI Guard panel as a Word Trusted Add-in Catalog
   7. Launches the app

 Run it (from anywhere):
     powershell -ExecutionPolicy Bypass -File "C:\Bylaw\cai-guard\packaging\install.ps1"
   or just double-click  packaging\install.bat

 Options:
     -NoBuild     reuse an existing dist\CAIGuard build, skip PyInstaller
     -NoAddin     don't register the Word panel
     -NoAutostart don't start with Windows
     -NoLaunch    don't launch at the end
     -Uninstall   remove everything this installer created
============================================================================
#>
[CmdletBinding()]
param(
  [switch]$NoBuild,
  [switch]$NoAddin,
  [switch]$NoAutostart,
  [switch]$NoLaunch,
  [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$AppName    = "CAI Guard"
$ExeName    = "CAIGuard.exe"
$RepoRoot   = Split-Path -Parent $PSScriptRoot
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\CAIGuard"
$StartMenu  = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$RunKey     = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$CatalogId  = "{B7B7A1E2-9C3D-4E6F-A012-3456789ABCDE}"
$CatalogKey = "HKCU:\Software\Microsoft\Office\16.0\WEF\TrustedCatalogs\$CatalogId"

function Info($m){ Write-Host "  $m" -ForegroundColor Cyan }
function Ok($m){   Write-Host "  $m" -ForegroundColor Green }
function Warn($m){ Write-Host "  $m" -ForegroundColor Yellow }
function Step($m){ Write-Host "`n== $m" -ForegroundColor White }

function New-Shortcut($lnkPath, $target, $desc){
  $ws = New-Object -ComObject WScript.Shell
  $s  = $ws.CreateShortcut($lnkPath)
  $s.TargetPath       = $target
  $s.WorkingDirectory = Split-Path -Parent $target
  $s.IconLocation     = $target
  $s.Description       = $desc
  $s.Save()
}

# ---------------------------------------------------------------- UNINSTALL
if ($Uninstall) {
  Step "Uninstalling $AppName"
  # stop a running instance
  Get-Process -Name "CAIGuard" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  Remove-Item (Join-Path $StartMenu "$AppName.lnk") -ErrorAction SilentlyContinue
  Remove-Item (Join-Path ([Environment]::GetFolderPath("Desktop")) "$AppName.lnk") -ErrorAction SilentlyContinue
  if (Test-Path $RunKey) { Remove-ItemProperty -Path $RunKey -Name "CAIGuard" -ErrorAction SilentlyContinue }
  if (Test-Path $CatalogKey) { Remove-Item $CatalogKey -Recurse -Force -ErrorAction SilentlyContinue }
  if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force -ErrorAction SilentlyContinue }
  Ok "Removed shortcuts, autostart, Word catalog, and program files."
  Warn "Your guarded-document baselines in %LOCALAPPDATA%\CAIGuard were left intact."
  return
}

Write-Host "`n  CAI Guard installer" -ForegroundColor White
Write-Host "  Repo: $RepoRoot"

# ---------------------------------------------------------------- 1. PYTHON
if (-not $NoBuild) {
  Step "Checking Python"
  $py = $null
  foreach ($c in @("python","py")) {
    try { & $c --version 2>&1 | Out-Null; if ($LASTEXITCODE -eq 0) { $py = $c; break } } catch {}
  }
  if (-not $py) {
    Warn "Python was not found. Install it from https://www.python.org/downloads/ (check 'Add to PATH'), then re-run."
    throw "Python not found."
  }
  Ok "Using '$py'."

  # -------------------------------------------------------------- 2. BUILD
  Step "Building $ExeName (this can take a couple of minutes)"
  Push-Location $RepoRoot
  try {
    $venv = Join-Path $RepoRoot ".buildenv"
    if (-not (Test-Path $venv)) { & $py -m venv $venv }
    $venvPy = Join-Path $venv "Scripts\python.exe"
    Info "Installing dependencies + PyInstaller..."
    & $venvPy -m pip install --upgrade pip  | Out-Null
    & $venvPy -m pip install -r "requirements.txt" pyinstaller | Out-Null
    Info "Running PyInstaller..."
    & $venvPy -m PyInstaller --noconfirm --clean "packaging\CAIGuard.spec"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
  } finally { Pop-Location }
  Ok "Build complete."
}

$BuildDir = Join-Path $RepoRoot "dist\CAIGuard"
if (-not (Test-Path (Join-Path $BuildDir $ExeName))) {
  throw "Build output not found at $BuildDir. Run without -NoBuild first."
}

# ---------------------------------------------------------------- 3. INSTALL
Step "Installing to $InstallDir"
Get-Process -Name "CAIGuard" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 400
if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item (Join-Path $BuildDir "*") $InstallDir -Recurse -Force
# ensure the add-in catalog folder is present alongside the exe
$addinSrc = Join-Path $RepoRoot "addin"
if (Test-Path $addinSrc) { Copy-Item $addinSrc (Join-Path $InstallDir "addin") -Recurse -Force }
$ExePath = Join-Path $InstallDir $ExeName
Ok "Files installed."

# ---------------------------------------------------------------- 4. SHORTCUTS
Step "Creating shortcuts"
New-Shortcut (Join-Path $StartMenu "$AppName.lnk") $ExePath "Local document change tracking & approval"
New-Shortcut (Join-Path ([Environment]::GetFolderPath("Desktop")) "$AppName.lnk") $ExePath "CAI Guard"
Ok "Start Menu + Desktop shortcuts created."

# ---------------------------------------------------------------- 5. AUTOSTART
if (-not $NoAutostart) {
  Step "Enabling start-at-sign-in"
  New-ItemProperty -Path $RunKey -Name "CAIGuard" -Value "`"$ExePath`"" -PropertyType String -Force | Out-Null
  Ok "Will start automatically when you sign in."
}

# ---------------------------------------------------------------- 6. WORD PANEL
if (-not $NoAddin) {
  Step "Registering the Word panel (Trusted Add-in Catalog)"
  $addinDir = Join-Path $InstallDir "addin"
  # Word's Shared-Folder catalog expects a UNC path. Create an SMB share when we can (needs elevation);
  # otherwise fall back to the local path and tell the user, so this never silently 'does nothing'.
  $catalogUrl = $addinDir
  $elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
              ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
  if ($elevated) {
    try {
      if (-not (Get-SmbShare -Name "CAIGuardAddin" -ErrorAction SilentlyContinue)) {
        New-SmbShare -Name "CAIGuardAddin" -Path $addinDir -ReadAccess "Everyone" | Out-Null
      }
      $catalogUrl = "\\$env:COMPUTERNAME\CAIGuardAddin"
      Ok "Shared the add-in folder as $catalogUrl"
    } catch { Warn "Could not create the network share ($($_.Exception.Message)); using the local path." }
  } else {
    Warn "Not elevated: Word usually needs the add-in folder on a network share for the panel to appear."
    Warn "Either re-run this script as Administrator, or right-click '$addinDir' -> Give access to -> share it, then set the catalog Url to that \\server\share path."
  }
  New-Item -Path $CatalogKey -Force | Out-Null
  New-ItemProperty -Path $CatalogKey -Name "Id"    -Value $CatalogId    -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $CatalogKey -Name "Url"   -Value $catalogUrl   -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $CatalogKey -Name "Flags" -Value 1             -PropertyType DWord  -Force | Out-Null

  # Primary, no-admin sideload: Office's developer key points straight at the manifest file, so the
  # ribbon button appears after a Word restart without any network share. (This is what makes the shield show.)
  $manifest = Join-Path $addinDir "manifest.xml"
  foreach ($ver in @("16.0","15.0")) {
    $devKey = "HKCU:\Software\Microsoft\Office\$ver\WEF\Developer"
    try {
      New-Item -Path $devKey -Force | Out-Null
      New-ItemProperty -Path $devKey -Name $manifest -Value $manifest -PropertyType String -Force | Out-Null
    } catch {}
  }
  Ok "Word panel registered (developer sideload). Fully quit Word, reopen your document — the CAI Guard shield appears on the Home tab. (Keep CAI Guard running so the panel can load.)"
}

# ---------------------------------------------------------------- 7. LAUNCH
if (-not $NoLaunch) {
  Step "Launching $AppName"
  Start-Process $ExePath
  Ok "Running — look for the shield in your system tray."
}

Write-Host "`n  Done. $AppName is installed." -ForegroundColor Green
Write-Host "  Uninstall anytime:  powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Uninstall`n" -ForegroundColor DarkGray
