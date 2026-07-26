; ==========================================================================
;  CAI Guard installer  (Inno Setup 6+)
;  Build the app first:   packaging\build.bat   -> dist\CAIGuard\
;  Then open this file in Inno Setup and click Compile (or: iscc packaging\CAIGuard.iss)
;  Produces:  packaging\Output\CAIGuard-Setup.exe
; ==========================================================================

#define AppName    "CAI Guard"
#define AppVer     "0.1.0"
#define AppExe     "CAIGuard.exe"
#define Publisher  "CAI Guard"
; A stable random GUID identifying this app's trusted add-in catalog folder:
#define CatalogId  "{{B7B7A1E2-9C3D-4E6F-A012-3456789ABCDE}"

[Setup]
AppId={{9E1D2C3B-4A56-47F8-90AB-CDEF01234567}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher={#Publisher}
DefaultDirName={autopf}\CAIGuard
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
OutputBaseFilename=CAIGuard-Setup
OutputDir=Output
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\assets\caiguard.ico

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startup";     Description: "Start CAI Guard automatically when I sign in"; GroupDescription: "Startup:"
Name: "wordaddin";   Description: "Enable the CAI Guard panel inside Microsoft Word"; GroupDescription: "Word integration:"

[Files]
; The entire PyInstaller one-folder build:
Source: "..\dist\CAIGuard\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; Ensure the add-in manifest folder is present for the Word trusted catalog:
Source: "..\addin\*"; DestDir: "{app}\addin"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}";               Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}";     Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";         Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Run at sign-in (per-user):
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "CAIGuard"; ValueData: """{app}\{#AppExe}"""; Flags: uninsdeletevalue; Tasks: startup

; Register {app}\addin as a Word Trusted Add-in Catalog so the ribbon panel appears.
; (Office 16.0 = Microsoft 365 / 2016-2021.)
Root: HKCU; Subkey: "Software\Microsoft\Office\16.0\WEF\TrustedCatalogs\{#CatalogId}"; \
  ValueType: string; ValueName: "Id";  ValueData: "{#CatalogId}"; Flags: uninsdeletekey; Tasks: wordaddin
Root: HKCU; Subkey: "Software\Microsoft\Office\16.0\WEF\TrustedCatalogs\{#CatalogId}"; \
  ValueType: string; ValueName: "Url"; ValueData: "{app}\addin"; Tasks: wordaddin
Root: HKCU; Subkey: "Software\Microsoft\Office\16.0\WEF\TrustedCatalogs\{#CatalogId}"; \
  ValueType: dword;  ValueName: "Flags"; ValueData: "1"; Tasks: wordaddin

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent
