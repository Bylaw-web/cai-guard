"""Local web app — the CAI Guard program window. Edits here write back into the .docx."""
import os, webbrowser, threading
from flask import Flask, request, jsonify, Response
from . import core, store, docx_io
from .engine import content_hash, semantic_hash, classify_section

def create_app(doc_path):
    app = Flask(__name__)
    DOC = os.path.abspath(doc_path)
    UI = os.path.join(os.path.dirname(__file__), "ui", "index.html")

    @app.before_request
    def _guard_host():
        # This UI has mutating endpoints (edit/approve/reject) — reject non-loopback Host headers
        # so a DNS-rebinding page can't drive them.
        host = (request.host or "").lower()
        hostname = host.rsplit(":", 1)[0].strip("[]")
        if hostname not in ("127.0.0.1", "localhost", "::1"):
            from flask import abort; abort(403)

    def state():
        manifest = store.load(DOC)
        secs = docx_io.read_sections(DOC)
        _, pending = core.verify(DOC)
        levels = {p["id"]: p["level"] for p in pending if p.get("cur")}
        out = []
        for s in secs:
            out.append({"id": s["id"], "heading": s["heading"],
                        "text": s["text"], "sh": content_hash(s["text"])[:4],
                        "mh": semantic_hash(s["text"])[:4],
                        "level": levels.get(s["id"], "none")})
        return {"name": os.path.basename(DOC), "path": DOC,
                "version": manifest["current_version"], "sections": out,
                "pending": pending, "history": manifest["history"][:30]}

    @app.get("/")
    def index():
        return Response(open(UI, encoding="utf-8").read(), mimetype="text/html")

    @app.get("/api/state")
    def api_state():
        return jsonify(state())

    @app.post("/api/edit")
    def api_edit():
        d = request.get_json()
        core.apply_edit(DOC, d["id"], d["text"])
        return jsonify({"ok": True})

    @app.post("/api/approve")
    def api_approve():
        core.approve(DOC, request.get_json()["id"]); return jsonify({"ok": True})

    @app.post("/api/reject")
    def api_reject():
        core.reject(DOC, request.get_json()["id"]); return jsonify({"ok": True})

    return app

def serve(doc_path, port=4600, open_browser=True):
    if not store.load(doc_path):
        core.enroll(doc_path)
        print(f"Enrolled + locked {os.path.basename(doc_path)}")
    app = create_app(doc_path)
    url = f"http://127.0.0.1:{port}/"
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print(f"CAI Guard running at {url}  (edit here or in Word — both stay in sync)")
    app.run(host="127.0.0.1", port=port)
