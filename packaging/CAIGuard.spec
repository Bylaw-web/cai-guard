# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for CAI Guard — windowed (no console) one-folder build.
# Build from the repo root:  pyinstaller packaging\CAIGuard.spec
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("addin", "addin"), ("caiguard/ui", "caiguard/ui"), ("assets", "assets")]
binaries = []
hiddenimports = collect_submodules("webview") + collect_submodules("pystray") + [
    "clr", "flask", "watchdog", "docx", "PIL", "PIL.Image", "PIL.ImageDraw",
]
for pkg in ("webview", "pystray"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

a = Analysis(
    ["run_app.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="CAIGuard",
    console=False,                       # windowed app — no PowerShell/console window
    icon="assets/caiguard.ico",
)
coll = COLLECT(exe, a.binaries, a.datas, name="CAIGuard")
