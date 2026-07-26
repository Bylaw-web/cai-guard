"""Background watch: detect edits made in Word and classify them (the daemon)."""
import os, time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from . import core, docx_io, store

class _H(FileSystemEventHandler):
    def __init__(self, doc_path):
        self.doc = os.path.abspath(doc_path); self.last = 0
    def _hit(self, path):
        if not path or docx_io.is_ignorable(path): return           # OneDrive/Word artifact
        if os.path.abspath(path) != self.doc: return
        if not docx_io.is_hydrated(self.doc): return                # cloud-only placeholder — don't force a download
        if time.time() - self.last < 1.0: return
        self.last = time.time(); time.sleep(0.4)
        try:
            _, pending = core.verify(self.doc)
        except Exception as ex:
            print("  (verify skipped:", ex, ")"); return
        if pending:
            print(f"[CAI] {len(pending)} pending change(s) after save:")
            for p in pending:
                print(f"   § {p['id']}  {p['level']}  ({p['actor']})")
        else:
            print("[CAI] save detected — no divergence from baseline.")
    # AutoSave replaces the file (temp + rename) -> also handle create/move, not just modify.
    def on_modified(self, e): self._hit(e.src_path)
    def on_created(self, e):  self._hit(e.src_path)
    def on_moved(self, e):    self._hit(getattr(e, "dest_path", None) or e.src_path)

def watch(doc_path):
    if store.load(doc_path) is None:      # only enroll if not already governed (never re-baseline)
        core.enroll(doc_path); print("Enrolled + locked.")
    obs = Observer(); obs.schedule(_H(doc_path), os.path.dirname(os.path.abspath(doc_path)), recursive=False)
    obs.start(); print(f"Watching {os.path.basename(doc_path)} — edit it in Word; Ctrl+C to stop.")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()
