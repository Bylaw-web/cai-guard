"""Native desktop app: persistent tray emblem + real app window (pywebview),
one-click add, on-screen setup, auto-alert on Word save, Ask AI, header/footer aware."""
import os, threading, json, time
from . import core, store, config, docx_io, ai
from .engine import content_hash, semantic_hash, classify_section

_window = None
_observer = None
_watch_handler = None
_watched_dirs = set()

def _ok(fn):
    try:
        return {"ok": True, **(fn() or {})}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _eligible(path):
    """A file we can enroll: a .docx/.md that isn't a temp/lock file or a guard sidecar."""
    b = os.path.basename(path)
    if b.startswith("~$") or b.startswith(".~") or b.startswith("."):
        return False
    if (os.sep + ".caiguard" + os.sep) in path:
        return False
    if not b.lower().endswith((".docx", ".md")):
        return False
    return os.path.isfile(path)

import re as _re
def _boundary(sec):
    t = sec["text"].strip()
    if sec.get("heading"): return True
    if _re.match(r"^(ARTICLE|SECTION|CLAUSE|PART|SCHEDULE|EXHIBIT|APPENDIX|RECITAL|WHEREAS)\b", t, _re.I): return True
    if _re.match(r"^\d+[.)]\s+\S", t): return True
    if _re.match(r"^[IVXLC]{1,6}[.)]\s+\S", t): return True
    letters = [c for c in t if c.isalpha()]
    if letters and t == t.upper() and len(t) < 80: return True
    return False
def _title(t):
    t = t.strip().split("\n")[0]
    return (t[:58] + "…") if len(t) > 58 else t
def _grouped(path, manifest):
    secs = docx_io.read_sections(path)
    try:
        _, pending = core.verify(path)
    except Exception:
        pending = []
    # per-current-section level, aligned by content (deletions carry no current id and are skipped here)
    levels = {p["id"]: p["level"] for p in pending if p.get("cur")}
    def item(s): return {"id": s["id"], "text": s["text"], "heading": s["heading"], "level": levels.get(s["id"], "none"), "region": s["region"]}
    body_secs = [s for s in secs if s["region"] == "body"]
    hdr = [item(s) for s in secs if s["region"] == "header"]
    ftr = [item(s) for s in secs if s["region"] == "footer"]
    has_boundary = any(_boundary(s) for s in body_secs)
    body = []
    if not has_boundary:
        body = [{"title": _title(s["text"]), "heading": False, "region": "body", "sections": [item(s)]} for s in body_secs]
    else:
        cur = None
        for s in body_secs:
            if _boundary(s) or cur is None:
                cur = {"title": _title(s["text"]), "heading": s["heading"], "region": "body", "sections": []}; body.append(cur)
            cur["sections"].append(item(s))
    groups = []
    if hdr: groups.append({"title": "Header", "heading": False, "region": "header", "sections": hdr})
    groups += body
    if ftr: groups.append({"title": "Footer", "heading": False, "region": "footer", "sections": ftr})
    for g in groups:
        txt = "\n".join(x["text"] for x in g["sections"])
        g["sh"] = content_hash(txt)[:4]; g["mh"] = semantic_hash(txt)[:4]
        g["changed"] = any(x["level"] not in ("none", None) for x in g["sections"])
    return groups

class Api:
    def pick_document(self):
        import webview
        res = _window.create_file_dialog(webview.OPEN_DIALOG,
              file_types=("Word document (*.docx)", "Markdown (*.md)", "All files (*.*)"))
        return res[0] if res else None

    def enroll(self, path):
        def go():
            core.enroll(path); config.add_enrolled(path)
            _watch_dir(os.path.dirname(os.path.abspath(path)))   # watch it now, no restart needed
            return {"name": os.path.basename(path)}
        return _ok(go)

    def pick_folder(self):
        import webview
        res = _window.create_file_dialog(webview.FOLDER_DIALOG)
        return res[0] if res else None

    def scan_folder(self, folder, recursive=True):
        """Count the not-yet-guarded documents under a folder (for the confirm dialog)."""
        found = []
        for root, _dirs, files in os.walk(folder):
            for fn in files:
                p = os.path.join(root, fn)
                if _eligible(p) and store.load(p) is None:
                    found.append(p)
            if not recursive:
                break
        return {"count": len(found), "sample": [os.path.basename(x) for x in found[:8]]}

    def enroll_folder(self, folder, recursive=True):
        """Digest a whole folder — CAI-lock every eligible document not already guarded."""
        def go():
            added = skipped = 0; failures = []
            for root, _dirs, files in os.walk(folder):
                for fn in files:
                    p = os.path.join(root, fn)
                    if not _eligible(p):
                        continue
                    if store.load(p) is not None:
                        skipped += 1; continue
                    try:
                        core.enroll(p); config.add_enrolled(p)
                        _watch_dir(os.path.dirname(os.path.abspath(p)))
                        added += 1
                    except Exception as ex:
                        failures.append({"name": os.path.basename(p), "error": str(ex)[:120]})
                if not recursive:
                    break
            return {"added": added, "skipped": skipped, "failed": len(failures), "failures": failures[:6]}
        return _ok(go)

    def list_docs(self):
        out = []
        for p in config.load_enrolled():
            if not os.path.exists(p): continue
            m = store.load(p)
            try: _, pend = core.verify(p)
            except Exception: pend = []
            out.append({"path": p, "name": os.path.basename(p),
                        "version": m["current_version"] if m else 1, "pending": len(pend)})
        return out

    def remove_doc(self, path): return _ok(lambda: core.unenroll(path) and {})

    def state(self, path):
        try:
            m = store.load(path)
            if not m:
                return {"name": os.path.basename(path), "path": path, "version": 1,
                        "groups": [], "pending": [], "history": [], "error": "Not enrolled."}
            _, pending = core.verify(path)
            return {"name": os.path.basename(path), "path": path, "version": m["current_version"],
                    "groups": _grouped(path, m), "pending": pending, "history": m["history"][:30]}
        except Exception as e:
            return {"name": os.path.basename(path), "path": path, "version": 1,
                    "groups": [], "pending": [], "history": [], "error": str(e)}

    def edit(self, path, sid, text): return _ok(lambda: core.apply_edit(path, sid, text) and {})
    def approve(self, path, sid):    return _ok(lambda: core.approve(path, sid) and {})
    def reject(self, path, sid):     return _ok(lambda: core.reject(path, sid) and {})
    def restore_locked(self, path):  return _ok(lambda: core.restore_locked(path) and {})
    def push_all(self, path):        return _ok(lambda: {"pushed": core.approve_all(path)})

    def scan_pending_all(self):
        """Summary of pending changes across all enrolled docs (for the bulk-push confirm)."""
        docs = 0; changed = 0; total = 0
        for p in config.load_enrolled():
            if not os.path.exists(p) or store.load(p) is None:
                continue
            docs += 1
            try:
                _, pend = core.verify(p)
                if pend:
                    changed += 1; total += len(pend)
            except Exception:
                pass
        return {"docs": docs, "changed": changed, "total": total}

    def push_all_docs(self):
        """Bulk-accept pending changes across every enrolled doc in one pass."""
        def go():
            res = core.push_all_enrolled()
            return {"docs": len(res),
                    "changed": sum(1 for r in res if r["ok"] and r.get("pushed", 0) > 0),
                    "pushed": sum(r.get("pushed", 0) for r in res if r["ok"]),
                    "failed": sum(1 for r in res if not r["ok"])}
        return _ok(go)

    # ---- structural integrity + dependency graph ----
    def check_integrity(self, path): return core.check_integrity(path)
    def accept_integrity(self, path): return _ok(lambda: core.accept_integrity(path) and {})
    def graph(self, path):           return core.graph(path)

    def ai_preview(self, path, msg):
        secs = docx_io.read_sections(path)
        return ai.propose(secs, msg, config.load_settings())

    def ai_apply(self, path, edits):
        errs = []
        for e in edits:
            try:
                # Bind each edit to the section whose CURRENT content matches the proposed hash,
                # so a save between preview and apply can't land it on the wrong paragraph.
                if e.get("old_content_hash"):
                    core.apply_hashed_edit(path, e["old_content_hash"], e["new"])
                else:
                    core.apply_edit(path, e["id"], e["new"])
            except Exception as ex:
                errs.append(str(ex))
        return {"ok": not errs, "applied": len(edits) - len(errs), "error": errs[0] if errs else None}

    def get_settings(self): return config.load_settings()
    def save_settings(self, s): config.save_settings(s); return {"ok": True}

    # ---- Semantic Library (vocab) ----
    def get_vocab(self): return config.load_vocab()
    def save_vocab(self, v):
        return _ok(lambda: (config.save_vocab(v), core.reload_engine(), {})[-1])
    def reset_vocab(self):
        return _ok(lambda: (config.reset_vocab(), core.reload_engine(), {})[-1])

    # ---- Lexicon (custom locked-meaning watchlist) ----
    def get_lexicon(self): return config.load_lexicon()
    def save_lexicon(self, items):
        return _ok(lambda: (config.save_lexicon(items or []), core.reload_engine(), {})[-1])


def _make_icon():
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.polygon([(32, 4), (58, 15), (58, 34), (32, 60), (6, 34), (6, 15)], fill=(14, 165, 233, 255))
    d.polygon([(32, 12), (50, 20), (50, 33), (32, 51), (14, 33), (14, 20)], fill=(11, 18, 32, 255))
    try: d.text((26, 24), "C", fill=(255, 255, 255, 255))
    except Exception: pass
    return img

def open_window():
    global _window
    import webview
    if _window is not None:
        try: _window.show(); return
        except Exception: pass
    ui = os.path.join(os.path.dirname(__file__), "ui", "app.html")
    _window = webview.create_window("CAI Guard", ui, js_api=Api(), width=1140, height=760, min_size=(900, 600))

def _start_watcher():
    """Auto-alert: when an enrolled document is saved (e.g. in Word), push an update to the UI."""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except Exception:
        return
    last = {}
    class H(FileSystemEventHandler):
        def _hit(self, path):
            if not path or docx_io.is_ignorable(path): return       # OneDrive/Word artifact
            p = os.path.abspath(path)
            enrolled = [os.path.abspath(x) for x in config.load_enrolled()]
            if p not in enrolled: return
            if not docx_io.is_hydrated(p): return                   # cloud-only placeholder — skip
            if time.time() - last.get(p, 0) < 1.2: return
            last[p] = time.time(); time.sleep(0.4)
            try: _, pend = core.verify(p)
            except Exception: pend = []
            try: integ = core.check_integrity(p)
            except Exception: integ = {"verdict": "ok", "alerts": []}
            if _window:
                try: _window.show()
                except Exception: pass
                if integ.get("verdict") == "corruption":
                    js = f"window.onIntegrityAlert && window.onIntegrityAlert({json.dumps(p)},{json.dumps(integ['alerts'])})"
                else:
                    js = f"window.onWordSave && window.onWordSave({json.dumps(p)},{len(pend)})"
                try: _window.evaluate_js(js)
                except Exception: pass
        # AutoSave replaces the file (temp + rename), so also listen for create/move, not just modify.
        def on_modified(self, e): self._hit(e.src_path)
        def on_created(self, e):  self._hit(e.src_path)
        def on_moved(self, e):    self._hit(getattr(e, "dest_path", None) or e.src_path)
    global _observer, _watch_handler, _watched_dirs
    _observer = Observer(); _watch_handler = H(); _watched_dirs = set()
    for x in config.load_enrolled():
        _watch_dir(os.path.dirname(os.path.abspath(x)))
    _observer.daemon = True; _observer.start()

def _watch_dir(d):
    """Schedule a folder for watching if not already — lets docs enrolled after startup be watched."""
    global _watched_dirs
    if _observer is None or not d or d in _watched_dirs:
        return
    try:
        _observer.schedule(_watch_handler, d, recursive=False)
        _watched_dirs.add(d)
    except Exception:
        pass

def run():
    import webview
    core.reload_engine()          # load the user's semantic library + lexicon before watching
    try:
        import pystray
        def _open(i, it): open_window()
        def _quit(i, it):
            i.stop()
            try: _window.destroy()
            except Exception: pass
            os._exit(0)
        icon = pystray.Icon("CAIGuard", _make_icon(), "CAI Guard",
                menu=pystray.Menu(pystray.MenuItem("Open CAI Guard", _open, default=True),
                                  pystray.MenuItem("Quit", _quit)))
        threading.Thread(target=icon.run, daemon=True).start()
    except Exception as e:
        print("(tray unavailable:", e, ")")
    threading.Timer(1.5, _start_watcher).start()
    try:
        from . import addin_server
        addin_server.start_background()          # backs the Word task pane at http://127.0.0.1:4620
    except Exception as e:
        print("(add-in service unavailable:", e, ")")
    open_window()
    webview.start()
