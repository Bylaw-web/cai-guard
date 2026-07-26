import sys, os, argparse
from . import core, store, __version__

def main(argv=None):
    ap = argparse.ArgumentParser(prog="caiguard", description="CAI Guard — local document change tracking & approval.")
    sub = ap.add_subparsers(dest="cmd")
    for c in ("enroll", "status", "verify", "watch"):
        sp = sub.add_parser(c); sp.add_argument("file")
    up = sub.add_parser("ui"); up.add_argument("file"); up.add_argument("--port", type=int, default=4600)
    sub.add_parser("app")   # native desktop app (tray + window)
    pa = sub.add_parser("push-all"); pa.add_argument("folder", nargs="?")   # bulk-accept pending across docs
    sub.add_parser("version")
    a = ap.parse_args(argv)

    if a.cmd == "enroll":
        m = core.enroll(a.file); print(f"Locked {m['doc_id']} — {len(m['sections'])} sections, v{m['current_version']}.")
    elif a.cmd == "status":
        m = store.load(a.file)
        if not m: print("Not enrolled."); return
        _, pend = core.verify(a.file)
        print(f"{m['doc_id']}  v{m['current_version']}  {len(m['sections'])} sections  {len(pend)} pending")
    elif a.cmd == "verify":
        _, pend = core.verify(a.file)
        if not pend: print("No divergence from the approved baseline.")
        for p in pend: print(f"  § {p['id']}  {p['level']:16}  ({p['actor']})  {p.get('cur','')[:60]}")
    elif a.cmd == "watch":
        from . import watcher; watcher.watch(a.file)
    elif a.cmd == "ui":
        from . import server; server.serve(a.file, port=a.port)
    elif a.cmd == "app":
        from . import app as desktop; desktop.run()
    elif a.cmd == "push-all":
        from . import config
        paths = config.load_enrolled()
        if a.folder:
            f = os.path.abspath(a.folder).lower()
            paths = [p for p in paths if os.path.abspath(p).lower().startswith(f)]
        res = core.push_all_enrolled(paths)
        changed = [r for r in res if r["ok"] and r.get("pushed", 0) > 0]
        pushed = sum(r.get("pushed", 0) for r in changed)
        fails = [r for r in res if not r["ok"]]
        print(f"Scanned {len(res)} doc(s) — {len(changed)} had changes, {pushed} change(s) accepted, {len(fails)} failure(s).")
        for r in changed:
            print(f"  pushed {r['pushed']:>3}  {os.path.basename(r['path'])}")
        for r in fails[:30]:
            print(f"  FAIL       {os.path.basename(r['path'])}: {r.get('error')}")
    elif a.cmd == "version":
        print("caiguard", __version__)
    else:
        ap.print_help()

if __name__ == "__main__":
    main()
