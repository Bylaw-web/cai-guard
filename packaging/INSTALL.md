# CAI Guard — build & install as a real Windows program

This turns CAI Guard from a `python -m caiguard` command into an installed app with a
Start-Menu/Desktop shortcut, optional run-at-sign-in, and a **CAI Guard panel inside Microsoft Word**.

## ⚡ Easiest: one-click install (no Inno Setup, no admin)
Double-click **`packaging\install.bat`**. It builds the app, installs it to your user profile,
creates the shortcuts, sets it to start at sign-in, registers the Word panel, and launches it —
all in one go. Only prerequisite is Python (python.org, "Add to PATH" checked).

To remove everything it installed:
```
powershell -ExecutionPolicy Bypass -File packaging\install.ps1 -Uninstall
```
Useful flags: `-NoBuild` (reuse an existing build), `-NoAddin`, `-NoAutostart`, `-NoLaunch`.

The manual route below (PyInstaller + Inno Setup) is still available if you'd rather produce a
shareable `CAIGuard-Setup.exe` to give to other people.

---

You only do the build once (or whenever the code changes). After that you just run the installer.

## Prerequisites (build machine)
- Windows 10/11, 64-bit
- Python 3.10+ (`python --version`)
- [Inno Setup 6+](https://jrsoftware.org/isdl.php) — for the installer step
- Microsoft Edge WebView2 runtime (already present on current Windows; the app uses it for its window)

## 1. Build the app (creates the .exe)
From the repo root (`C:\Bylaw\cai-guard`), double-click or run:

```
packaging\build.bat
```

This makes a private build environment, installs dependencies + PyInstaller, and produces a
windowed program (no console window):

```
dist\CAIGuard\CAIGuard.exe
```

You can already double-click that .exe — it launches to the system tray with the shield icon.

## 2. Build the installer
Open `packaging\CAIGuard.iss` in Inno Setup and click **Compile** (or run `iscc packaging\CAIGuard.iss`).
Result:

```
packaging\Output\CAIGuard-Setup.exe
```

Give that file to any Windows user. Running it installs CAI Guard like normal software, with
checkboxes for a desktop shortcut, run-at-sign-in, and the Word panel. It installs per-user, so
**no administrator rights are required**. Uninstall from Settings → Apps like any program.

## 3. Turn on the Word panel
The installer (with the "Enable the CAI Guard panel inside Microsoft Word" box checked) registers
`{app}\addin` as a **Word Trusted Add-in Catalog**. To finish:

1. Make sure **CAI Guard is running** (tray shield visible) — the panel loads its content from the
   local service at `http://127.0.0.1:4620`, which only runs while the app is open.
2. Open Word → **File ▸ Options ▸ Trust Center ▸ Trust Center Settings ▸ Trusted Add-in Catalogs** →
   confirm the CAI Guard folder is listed and **Show in Menu** is checked → OK → restart Word.
3. In Word: **Insert ▸ My Add-ins ▸ Shared Folder ▸ CAI Guard**. A **shield button** appears on the
   Home tab. Click it to open the panel.

### What the panel shows
- A green shield + "Protected — in sync" when the open document matches its approved baseline.
- An amber shield with counts (**Weakened / Semantic / Structural / Cosmetic**) and a list of the
  pending changes when it has diverged — including the exact obligation downgrade (e.g. `MUST → MAY`).
- A grey shield + "Not protected" if the document isn't enrolled yet.
- "CAI Guard is not running" if the tray app is closed.

## Notes on the "Grammarly-style" icon
Microsoft Word does not let any program (Grammarly included) draw a live, clickable icon floating in
the document text. The sanctioned in-Word surfaces are the **ribbon button + task pane** used here.
It's persistent, shows live stats, and travels with the document — the same mechanism Grammarly's
Office integration uses. The floating bubble Grammarly shows in *other* apps is a separate
system-wide overlay, not something inside the Word document.

## Fallback sideload (no installer)
If you skipped the installer and just want to test the panel:
1. Run `CAIGuard.exe` (or `python -m caiguard app`).
2. Word ▸ File ▸ Options ▸ Trust Center ▸ Trusted Add-in Catalogs → add the full path to the
   repo's `addin` folder → Show in Menu → OK → restart Word.
3. Insert ▸ My Add-ins ▸ Shared Folder ▸ CAI Guard.
