"""Frozen-app entry point (used by PyInstaller). Launches the tray + window app."""
from caiguard import app
if __name__ == "__main__":
    app.run()
