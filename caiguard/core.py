"""Enroll / verify / approve / reject / program-edit — CAI lifecycle over a real doc."""
import os, shutil
from . import store, docx_io, integrity
from . import engine
from .engine import content_hash, semantic_hash, classify_section, advise, align_sequences

def reload_engine():
    """Reconfigure the deterministic engine from the user's saved semantic library + lexicon.
    Call at startup and after either is edited in Settings."""
    try:
        from . import config
        engine.configure(config.load_vocab(), config.load_lexicon())
    except Exception:
        engine.configure()   # fall back to built-in defaults

def unenroll(doc_path):
    """Unlock a document: remove its baseline/vault and drop it from the enrolled list."""
    from . import config
    try:
        shutil.rmtree(store._dir(doc_path), ignore_errors=True)
    except Exception:
        pass
    config.remove_enrolled(doc_path)
    return True

def _align(manifest, current):
    """Return (pairs, base_by_cur, cur_by_id). pairs from align_sequences over texts."""
    base = manifest["sections"]
    pairs = align_sequences([b["baseline"] for b in base], [c["text"] for c in current])
    base_by_cur = {cj: bi for (bi, cj) in pairs if cj is not None}
    cur_by_id = {c["id"]: idx for idx, c in enumerate(current)}
    return pairs, base_by_cur, cur_by_id

def enroll(doc_path):
    secs = docx_io.read_sections(doc_path)
    manifest = {
        "doc_id": os.path.basename(doc_path), "path": os.path.abspath(doc_path),
        "recognizer": "docx@1.1" if docx_io.is_docx(doc_path) else "md@1.0",
        "locked_at": store.now(), "current_version": 1, "baseline_version": 1,
        "sections": [{"id": s["id"], "region": s["region"], "heading": s["heading"],
                      "baseline": s["text"], "content_hash": content_hash(s["text"]),
                      "semantic_hash": semantic_hash(s["text"])} for s in secs],
        "history": [{"ts": store.now(), "event": "enrolled", "sections": len(secs)}],
        "actors": {},
        "integrity": integrity.snapshot(doc_path) if docx_io.is_docx(doc_path) else None,
    }
    store.snapshot_bytes(doc_path, 1)
    store.save(doc_path, manifest)
    return manifest

def _reseal_integrity(doc_path, manifest):
    """Re-lock the structural baseline to the current file (called when changes are accepted)."""
    if docx_io.is_docx(doc_path):
        manifest["integrity"] = integrity.snapshot(doc_path)

def check_integrity(doc_path):
    """Structural verdict for the current file vs the locked snapshot. Returns {verdict, alerts, root}."""
    manifest = store.load(doc_path)
    if not manifest or not docx_io.is_docx(doc_path):
        return {"verdict": "ok", "alerts": [], "root": None}
    return integrity.check(doc_path, manifest.get("integrity") or {})

def graph(doc_path):
    """Dependency map payload for the Graph tab."""
    manifest = store.load(doc_path)
    base = (manifest or {}).get("integrity") or None
    return integrity.graph(doc_path, base)

def accept_integrity(doc_path):
    """User chose 'Push' on a structural alert: trust the current structure as the new locked baseline."""
    manifest = store.load(doc_path)
    if not manifest:
        raise RuntimeError("Document is not enrolled.")
    _reseal_integrity(doc_path, manifest)
    manifest["current_version"] += 1
    store.snapshot_bytes(doc_path, manifest["current_version"])
    manifest["baseline_version"] = manifest["current_version"]
    manifest["history"].insert(0, {"ts": store.now(), "event": "structure_accepted",
                                   "version": manifest["current_version"]})
    store.save(doc_path, manifest)
    return True

def verify(doc_path):
    manifest = store.load(doc_path)
    if not manifest:
        raise RuntimeError("Document is not enrolled.")
    base = manifest["sections"]
    cur = docx_io.read_sections(doc_path)
    pairs, _, _ = _align(manifest, cur)
    pending = []
    for bi, cj in pairs:
        if bi is not None and cj is not None:
            bs, cs = base[bi], cur[cj]
            r = classify_section(bs["baseline"], cs["text"])
            if r["level"] != "none":
                item = {"id": cs["id"], "base_id": bs["id"], "region": cs["region"],
                        "level": "control-weakened" if r.get("weak") else r["level"],
                        "weak": r.get("weak"), "diffs": r.get("diffs", []),
                        "base": bs["baseline"], "cur": cs["text"],
                        "actor": manifest["actors"].get(cs["id"], "word")}
                if r["level"] == "cosmetic":
                    item["advisory"] = advise(bs["baseline"], cs["text"])
                pending.append(item)
        elif cj is not None:                                   # inserted paragraph
            cs = cur[cj]
            pending.append({"id": cs["id"], "base_id": None, "region": cs["region"],
                            "level": "structural", "base": "", "cur": cs["text"],
                            "actor": manifest["actors"].get(cs["id"], "word"),
                            "diffs": [], "detail": "new section"})
        else:                                                  # removed paragraph
            bs = base[bi]
            # Use a REMOVAL-namespaced id ("rm:<baseline index>") so it can never collide with a
            # current paragraph's positional id (which, after a deletion, names a different section).
            pending.append({"id": "rm:%d" % bi, "base_id": bs["id"], "region": bs.get("region", "body"),
                            "level": "structural", "base": bs["baseline"], "cur": "",
                            "actor": "word", "diffs": [], "detail": "section removed"})
    return manifest, pending

def apply_edit(doc_path, section_id, new_text):
    manifest = store.load(doc_path)
    docx_io.write_section(doc_path, section_id, new_text)   # -> visible in Word
    manifest["actors"][section_id] = "program"
    store.save(doc_path, manifest)
    return True

def apply_hashed_edit(doc_path, old_content_hash, new_text):
    """Apply an edit bound to the section whose CURRENT content matches old_content_hash.

    This is how AI proposals are written: the edit lands on the section it was computed against,
    not a fragile positional id — if the doc changed since the proposal, it refuses rather than
    writing to the wrong paragraph.
    """
    if not old_content_hash or len(old_content_hash) < 12:
        raise RuntimeError("Edit is not bound to a section hash — re-run Ask AI.")
    manifest = store.load(doc_path)
    cur = docx_io.read_sections(doc_path)
    matches = [c for c in cur if content_hash(c["text"]).startswith(old_content_hash)]
    if not matches:
        raise RuntimeError("That section changed since the edit was proposed — re-run Ask AI.")
    if len(matches) > 1:
        raise RuntimeError("The proposed edit is ambiguous (identical sections) — edit it directly.")
    sid = matches[0]["id"]
    docx_io.write_section(doc_path, sid, new_text)
    manifest["actors"][sid] = "program"
    store.save(doc_path, manifest)
    return True

def approve(doc_path, section_id):
    """Accept the current text of one section (identified by its current id) into the baseline.

    Alignment-aware: an edited paragraph updates its matched baseline entry even if the
    paragraph moved; an inserted paragraph is added; approving a removed baseline id drops it.
    """
    manifest = store.load(doc_path)
    base = manifest["sections"]
    cur = docx_io.read_sections(doc_path)
    pairs, base_by_cur, cur_by_id = _align(manifest, cur)

    if section_id.startswith("rm:"):                          # approving a REMOVAL (baseline index)
        idx = int(section_id[3:])
        removed = {bi for (bi, cj) in pairs if cj is None}
        if idx not in removed:
            raise RuntimeError("That removal was already resolved.")
        base.pop(idx)
        manifest["history"].insert(0, {"ts": store.now(), "event": "approved_removal", "section": section_id})
    else:
        cj = cur_by_id.get(section_id)
        if cj is None:
            raise RuntimeError("Unknown section")
        cs = cur[cj]
        new_text = cs["text"]
        bi = base_by_cur.get(cj)
        sec = base[bi] if bi is not None else None
        if sec is None:                                        # inserted paragraph -> new baseline entry
            sec = {"id": cs["id"], "region": cs["region"], "heading": cs["heading"]}
            base.insert(min(cj, len(base)), sec)
        sec["id"] = cs["id"]                                   # keep positional locator current
        sec["region"] = cs["region"]; sec["heading"] = cs["heading"]
        sec["baseline"] = new_text
        sec["content_hash"] = content_hash(new_text)
        sec["semantic_hash"] = semantic_hash(new_text)
        manifest["actors"].pop(section_id, None)
        manifest["history"].insert(0, {"ts": store.now(), "event": "approved",
                                       "section": section_id, "version": manifest["current_version"] + 1})

    manifest["current_version"] += 1
    store.save(doc_path, manifest)                     # persist the approved baseline first
    # Only re-vault a new byte-exact "locked" copy when NOTHING is still pending — otherwise a
    # partial approval would bake unapproved (possibly control-weakened) changes into the copy that
    # "Restore to locked" trusts. Until then the baseline keeps pointing at the last clean vault.
    m2, remaining = verify(doc_path)
    if not remaining:
        # Fully clean: renumber baseline ids to the current doc's ids so none are duplicated/stale.
        cur2 = docx_io.read_sections(doc_path)
        if len(cur2) == len(m2["sections"]):
            for sec, c in zip(m2["sections"], cur2):
                sec["id"] = c["id"]
        _reseal_integrity(doc_path, m2)
        store.snapshot_bytes(doc_path, m2["current_version"])
        m2["baseline_version"] = m2["current_version"]
        store.save(doc_path, m2)
    return True

def reject(doc_path, section_id):
    """Restore the baseline text of a section into the real document (undo in Word).

    section_id is the current paragraph id; its true prior text is found by alignment,
    so a reject still works after other paragraphs were inserted or removed.
    """
    manifest = store.load(doc_path)
    if section_id.startswith("rm:"):
        raise RuntimeError("This paragraph was deleted. Use 'Restore to locked' to bring back removed content.")
    cur = docx_io.read_sections(doc_path)
    pairs, base_by_cur, cur_by_id = _align(manifest, cur)
    cj = cur_by_id.get(section_id)
    if cj is None:
        raise RuntimeError("Unknown or already-removed section; use Restore to locked.")
    bi = base_by_cur.get(cj)
    if bi is None:
        raise RuntimeError("This is a newly-added section; use Restore to locked to remove it.")
    docx_io.write_section(doc_path, section_id, manifest["sections"][bi]["baseline"])
    manifest["actors"].pop(section_id, None)
    manifest["history"].insert(0, {"ts": store.now(), "event": "rejected", "section": section_id})
    store.save(doc_path, manifest)
    return True

def restore_locked(doc_path):
    import shutil
    manifest = store.load(doc_path)
    v = manifest.get("baseline_version", 1)
    try:
        shutil.copy2(store.vault_path(doc_path, v), doc_path)
    except PermissionError:
        raise RuntimeError("The document is open in Microsoft Word. Close it, then Restore.")
    except FileNotFoundError:
        raise RuntimeError("The locked byte-copy is missing, so there's nothing to restore. "
                           "Approve the current state to create a fresh lock.")
    manifest["actors"] = {}
    manifest["history"].insert(0, {"ts": store.now(), "event": "restored_to_locked", "version": v})
    store.save(doc_path, manifest)
    return True

def approve_all(doc_path):
    """Accept every pending change into the baseline with no per-item review (the 'Push changes' path).

    Re-baselines from the current document in one shot, so it is immune to index shifts.
    """
    manifest, pending = verify(doc_path)
    cur = docx_io.read_sections(doc_path)
    manifest["sections"] = [{"id": c["id"], "region": c["region"], "heading": c["heading"],
                             "baseline": c["text"], "content_hash": content_hash(c["text"]),
                             "semantic_hash": semantic_hash(c["text"])} for c in cur]
    manifest["current_version"] += 1; manifest["actors"] = {}
    _reseal_integrity(doc_path, manifest)
    manifest["history"].insert(0, {"ts": store.now(), "event": "pushed_all", "count": len(pending), "version": manifest["current_version"]})
    store.snapshot_bytes(doc_path, manifest["current_version"]); manifest["baseline_version"] = manifest["current_version"]
    store.save(doc_path, manifest)
    return len(pending)

def push_all_enrolled(paths=None):
    """Bulk 'Push changes': accept every pending change across many docs at once.

    paths=None -> all enrolled docs. Returns a per-doc result list. Docs with nothing pending are
    a no-op (pushed: 0). Never raises for one bad doc — it's recorded and the batch continues.
    """
    from . import config
    paths = paths or config.load_enrolled()
    results = []
    for p in paths:
        if not os.path.exists(p):
            results.append({"path": p, "ok": False, "error": "source file missing"}); continue
        if store.load(p) is None:
            results.append({"path": p, "ok": False, "error": "not enrolled"}); continue
        try:
            results.append({"path": p, "ok": True, "pushed": approve_all(p)})
        except Exception as e:
            results.append({"path": p, "ok": False, "error": str(e)})
    return results
