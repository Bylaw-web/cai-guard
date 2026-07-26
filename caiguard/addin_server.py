"""Always-on localhost service that backs the Word Office Add-in.

Serves the task-pane web content and a small JSON API that maps the document currently
open in Word to an enrolled document and returns live CAI stats. Runs in a daemon thread
inside the tray app so the panel works whenever CAI Guard is running.

Same-origin by design: the task pane is served from here, so its fetch() calls need no CORS.
Bound to 127.0.0.1 only. Office permits http on localhost for add-in content.
"""
import os, sys, threading
from urllib.parse import unquote
from flask import Flask, request, jsonify, send_from_directory
from . import core, store, config

PORT = 4620

def _res(*parts):
    """Resolve a bundled resource both in source layout and inside a PyInstaller build."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, *parts)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), *parts)

ADDIN_DIR = _res("addin")

def _match(doc):
    """Map a Word document identity (path, file:// URL, or bare name) to an enrolled path."""
    if not doc:
        return None
    d = unquote(doc).strip()
    if d.lower().startswith("file:///"):
        d = d[8:]
    d = d.replace("/", os.sep)
    enrolled = config.load_enrolled()
    ab = os.path.abspath(d).lower()
    for p in enrolled:
        if os.path.abspath(p).lower() == ab:
            return p
    base = os.path.basename(d).lower()
    cands = [p for p in enrolled if os.path.basename(p).lower() == base]
    return cands[0] if cands else None

def _stats(doc_path):
    # Integrity first — it reads the raw zip and survives even a file Word can't open.
    try:
        integ = core.check_integrity(doc_path)
    except Exception:
        integ = {"verdict": "ok", "alerts": []}
    try:
        m, pending = core.verify(doc_path)
        version = m["current_version"]
    except Exception:
        pending = []
        version = (store.load(doc_path) or {}).get("current_version", 1)
    def n(pred): return sum(1 for x in pending if pred(x))
    items = [{"id": x["id"], "level": x["level"],
              "text": (x.get("cur") or x.get("base") or "")[:90],
              "weak": x.get("weak")} for x in pending[:12]]
    return {"enrolled": True, "name": os.path.basename(doc_path),
            "version": version, "pending": len(pending),
            "weakened":   n(lambda x: x["level"] == "control-weakened"),
            "semantic":   n(lambda x: x["level"] == "semantic"),
            "structural": n(lambda x: x["level"] == "structural"),
            "cosmetic":   n(lambda x: x["level"] == "cosmetic"),
            "items": items,
            "integrity": integ.get("verdict", "ok"),
            "alerts": [{"name": a["name"], "detail": a["detail"], "sev": a["sev"]}
                       for a in integ.get("alerts", []) if a.get("sev") == "critical"]}

def create_app():
    app = Flask(__name__)

    @app.before_request
    def _guard_host():
        # Reject any request whose Host header isn't a loopback name (port-agnostic). This blocks
        # DNS-rebinding: a remote page can't point its own hostname at 127.0.0.1 and read data.
        from flask import request as _rq, abort
        host = (_rq.host or "").lower()
        hostname = host.rsplit(":", 1)[0].strip("[]")
        if hostname not in ("127.0.0.1", "localhost", "::1"):
            abort(403)

    @app.get("/api/addin/ping")
    def ping():
        return jsonify({"ok": True, "service": "caiguard", "docs": len(config.load_enrolled())})

    @app.get("/api/addin/state")
    def state():
        doc = request.args.get("doc", "")
        p = _match(doc)
        if not p or not store.load(p):
            return jsonify({"enrolled": False, "name": os.path.basename(unquote(doc)) if doc else ""})
        try:
            return jsonify(_stats(p))
        except Exception as e:
            return jsonify({"enrolled": True, "error": str(e), "pending": 0})

    @app.get("/")
    def root():
        return send_from_directory(ADDIN_DIR, "taskpane.html")

    @app.get("/<path:fname>")
    def asset(fname):
        return send_from_directory(ADDIN_DIR, fname)

    return app

def serve(port=PORT, block=True):
    app = create_app()
    app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False)

def start_background(port=PORT):
    """Launch the service in a daemon thread; safe to call once from the tray app."""
    t = threading.Thread(target=serve, kwargs={"port": port}, daemon=True)
    t.start()
    return t
