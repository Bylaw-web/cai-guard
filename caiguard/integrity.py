"""Structural integrity for .docx packages — corruption detection & a dependency map.

A .docx is an OPC zip of XML *parts* wired together by relationship (.rels) files.
This module treats each part as an atom (byte content_hash) and each relationship as
an edge, then computes a COMPOSITIONAL rollup (a Merkle root — a parent's hash is a pure
function of its children's hashes, so tampering anywhere changes the root). Comparing a fresh
walk to the locked snapshot yields NAMED alerts (dropped part, broken relationship, unreadable part, …).

Pure stdlib: zipfile + xml.etree + hashlib. No AI, no third-party deps.
"""
import os, zipfile, hashlib
import xml.etree.ElementTree as ET

def _sha(b): return hashlib.sha256(b if isinstance(b, bytes) else b.encode("utf-8")).hexdigest()

# Friendly names for the OOXML parts users actually care about losing.
_FRIENDLY = {
    "word/document.xml": "the main document body",
    "word/comments.xml": "comments",
    "word/footnotes.xml": "footnotes",
    "word/endnotes.xml": "endnotes",
    "word/numbering.xml": "list numbering",
    "word/styles.xml": "styles",
    "word/settings.xml": "document settings",
    "word/people.xml": "tracked-change authors",
    "word/fontTable.xml": "fonts",
    "docProps/core.xml": "core properties",
    "docProps/app.xml": "app properties",
    "[Content_Types].xml": "the content-type map",
}
def describe(part):
    if part in _FRIENDLY: return _FRIENDLY[part]
    if part.startswith("word/media/"): return "an embedded image/media file (" + os.path.basename(part) + ")"
    if part.startswith("word/header"): return "a page header"
    if part.startswith("word/footer"): return "a page footer"
    if "comments" in part: return "comments data"
    if "footnote" in part: return "footnotes data"
    return part

def _source_of_rels(relname):
    """The part a .rels file governs.  word/_rels/document.xml.rels -> word/document.xml ; _rels/.rels -> ''."""
    d = os.path.dirname(relname)                 # e.g. word/_rels
    base = os.path.basename(relname)[:-5]        # strip '.rels'  -> document.xml  (or '' for .rels)
    parent = os.path.dirname(d)                  # e.g. word
    if base == "":
        return ""                                # package root
    return (parent + "/" if parent else "") + base

def _resolve(src, tgt):
    base = os.path.dirname(src)
    return os.path.normpath(os.path.join(base, tgt)).replace("\\", "/").lstrip("/")

def read_package(path):
    """Byte-hash every part, parse every .rels into edges, flag unreadable/zero-byte/malformed parts."""
    try:
        zf = zipfile.ZipFile(path)
    except Exception as e:
        return {"ok": False, "fatal": "INVALID_PACKAGE", "detail": str(e)}
    parts, edges, errors = {}, [], []
    try:
        for n in zf.namelist():
            if n.endswith("/"):
                continue
            try:
                b = zf.read(n)
            except Exception as e:
                errors.append([n, "read:" + str(e)[:60]]); continue
            parts[n] = {"hash": _sha(b), "size": len(b)}
            if n.endswith(".xml") or n.endswith(".rels"):
                if len(b) == 0:
                    errors.append([n, "zero-byte"])
                else:
                    try:
                        root = ET.fromstring(b)
                    except Exception as e:
                        errors.append([n, "xml:" + str(e)[:60]]); root = None
                    if root is not None and n.endswith(".rels"):
                        src = _source_of_rels(n)
                        for rel in root:
                            rid = rel.get("Id"); typ = (rel.get("Type") or "").rstrip("/").split("/")[-1]
                            tgt = rel.get("Target") or ""; mode = rel.get("TargetMode", "Internal")
                            if mode == "External":
                                edges.append([src, rid, typ, "EXTERNAL:" + tgt])
                            else:
                                edges.append([src, rid, typ, _resolve(src, tgt)])
    finally:
        zf.close()
    return {"ok": True, "parts": parts, "edges": edges, "errors": errors}

def build_map(path):
    """Full structural map + compositional Merkle rollup root."""
    pkg = read_package(path)
    if not pkg["ok"]:
        return pkg
    parts, edges = pkg["parts"], pkg["edges"]
    adj = {}
    for s, rid, typ, tgt in edges:
        adj.setdefault(s, []).append({"id": rid, "type": typ, "target": tgt})
    memo = {}
    def node_hash(part, stack):
        if part in memo: return memo[part]
        own = "ROOT" if part == "" else parts.get(part, {}).get("hash", "MISSING")
        if part in stack:                        # cycle guard: fall back to own bytes
            return own
        stack = stack | {part}
        kids = []
        for e in sorted(adj.get(part, []), key=lambda x: (x["type"], str(x["target"]), str(x["id"]))):
            t = e["target"]
            if isinstance(t, str) and t.startswith("EXTERNAL:"):
                kids.append(e["type"] + ":" + t)
            else:
                kids.append(e["type"] + ":" + node_hash(t, stack))
        h = _sha("|".join([own] + kids))
        memo[part] = h
        return h
    reachable = node_hash("", set())
    # Fold a hash of EVERY part (sorted name:hash) into the root so a tampered part that no
    # relationship points to still changes the root — the rollup must cover the whole package.
    allparts = _sha("|".join(sorted("%s:%s" % (k, v["hash"]) for k, v in parts.items())))
    root = _sha(reachable + "|ALL:" + allparts)
    return {"ok": True, "parts": parts, "edges": edges, "errors": pkg["errors"], "adj": adj, "root": root}

def snapshot(path):
    """Compact, JSON-serializable integrity record to store as the locked baseline."""
    m = build_map(path)
    if not m.get("ok"):
        return {"ok": False, "fatal": m.get("fatal"), "detail": m.get("detail")}
    return {"ok": True, "root": m["root"], "parts": m["parts"], "edges": m["edges"], "errors": m["errors"]}

# ---- alert names (stable ids the UI keys on) ----
ALERT_NAMES = {
    "INVALID_PACKAGE":  "Invalid package",
    "UNREADABLE_PART":  "Unreadable part",
    "DROPPED_PART":     "Dropped part",
    "DANGLING_REL":     "Broken relationship",
    "STRUCTURE_GUTTED": "Structure gutted",
    "STRUCT_DRIFT":     "Structure changed",
    "SIZE_ANOMALY":     "Size anomaly",
}
def _alert(t, sev, detail, part=None):
    return {"type": t, "name": ALERT_NAMES[t], "sev": sev, "detail": detail, "part": part}

# Parts whose disappearance is genuine corruption vs. a normal editing action.
_CRITICAL_PARTS = {"word/document.xml", "[Content_Types].xml", "word/styles.xml", "word/settings.xml"}
def _drop_is_critical(part):
    if part in _CRITICAL_PARTS or part.endswith(".rels"):
        return True
    # comments / foot-endnotes / media / headers / footers / people / fonts are legitimately removable
    return False

def diff(base, cur):
    """Compare a fresh map (cur) to the locked snapshot (base). Returns (alerts, verdict)."""
    if not cur.get("ok"):
        return [_alert("INVALID_PACKAGE", "critical",
                       cur.get("detail", "The file is not a readable .docx package."))], "corruption"
    alerts = []
    bparts, cparts = set(base.get("parts", {})), set(cur.get("parts", {}))

    for p in sorted(bparts - cparts):
        crit = _drop_is_critical(p)
        alerts.append(_alert("DROPPED_PART", "critical" if crit else "warn",
                             describe(p).capitalize() + " was in the locked version and is now "
                             + ("missing." if crit else "gone (a normal edit if you deleted it on purpose)."), p))

    for n, err in cur.get("errors", []):
        if err.startswith("zero-byte"):
            alerts.append(_alert("UNREADABLE_PART", "critical", n + " is zero bytes (truncated write).", n))
        elif err.startswith("xml:") or err.startswith("rels:") or err.startswith("read:"):
            alerts.append(_alert("UNREADABLE_PART", "critical", n + " could not be parsed (" + err + ").", n))

    cset = cparts
    seen = set()
    for s, rid, typ, tgt in cur.get("edges", []):
        if isinstance(tgt, str) and tgt.startswith("EXTERNAL:"):
            continue
        if tgt not in cset and tgt not in seen:
            seen.add(tgt)
            alerts.append(_alert("DANGLING_REL", "critical",
                                 (s or "package") + " points to " + str(rid) + " → " + str(tgt) + ", but that part is missing.", tgt))

    if bparts and len(cparts) < max(3, 0.6 * len(bparts)):
        alerts.append(_alert("STRUCTURE_GUTTED", "critical",
                             "Dropped from %d internal parts to %d — the document was likely rebuilt from plain text."
                             % (len(bparts), len(cparts))))

    verdict = "corruption" if any(a["sev"] == "critical" for a in alerts) else "ok"
    if verdict == "ok" and base.get("root") and cur.get("root") != base.get("root"):
        alerts.append(_alert("STRUCT_DRIFT", "warn",
                             "Internal structure changed (parts were edited) but no corruption was found."))
    return alerts, verdict

def check(path, base):
    cur = snapshot(path)
    alerts, verdict = diff(base or {}, cur)
    return {"verdict": verdict, "alerts": alerts, "root": cur.get("root")}

def graph(path, base=None):
    """Node/edge payload for the Graph tab, annotated with status vs the locked snapshot."""
    m = build_map(path)
    if not m.get("ok"):
        return {"ok": False, "fatal": m.get("fatal"), "detail": m.get("detail")}
    bparts = set((base or {}).get("parts", {}))
    bhash = {k: v.get("hash") for k, v in (base or {}).get("parts", {}).items()}
    cparts = set(m["parts"])
    err_parts = {e[0] for e in m["errors"]}
    tgt_present = cparts

    nodes = []
    for name, meta in sorted(m["parts"].items()):
        if name in err_parts:               status = "unreadable"
        elif base and name not in bparts:    status = "added"
        elif base and bhash.get(name) != meta["hash"]: status = "edited"
        else:                                status = "ok"
        nodes.append({"id": name, "kind": _kind(name), "hash": meta["hash"][:8],
                      "size": meta["size"], "label": describe(name), "status": status})
    # dropped parts (in baseline, gone now) shown as ghost nodes
    for name in sorted(bparts - cparts):
        nodes.append({"id": name, "kind": _kind(name), "hash": (bhash.get(name) or "")[:8],
                      "size": 0, "label": describe(name), "status": "dropped"})

    edges = []
    for s, rid, typ, tgt in m["edges"]:
        ext = isinstance(tgt, str) and tgt.startswith("EXTERNAL:")
        st = "external" if ext else ("dangling" if tgt not in tgt_present else "ok")
        edges.append({"source": s or "[package]", "target": (tgt if not ext else tgt), "type": typ, "id": rid, "status": st})
    # normalize root source label as a node too
    if any(e["source"] == "[package]" for e in edges):
        nodes.insert(0, {"id": "[package]", "kind": "root", "hash": (m["root"] or "")[:8],
                         "size": 0, "label": "package root", "status": "root"})
    return {"ok": True, "root": m["root"], "nodes": nodes, "edges": edges,
            "counts": {"parts": len(m["parts"]), "edges": len(m["edges"])}}

def _kind(name):
    if name == "[Content_Types].xml": return "meta"
    if name.startswith("word/media/"): return "media"
    if name.endswith(".rels"): return "rels"
    if name.startswith("docProps/"): return "props"
    if name.startswith("word/"): return "word"
    return "other"
