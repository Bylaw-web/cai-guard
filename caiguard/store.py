"""Per-document manifest (.cai.json) + byte vault.

Stored in a machine-local app-data folder (NOT next to the document), so that when the
document lives in OneDrive/Dropbox/iCloud the guard's baseline snapshots don't sync,
don't bloat the cloud folder, and can't spawn "conflicted copy" files across machines.
A legacy sidecar found next to the document is migrated here on first access.
"""
import os, json, hashlib, shutil, datetime, threading

_SAVE_LOCK = threading.RLock()

def _local_root():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "CAIGuard", "docs")

def _key(doc_path):
    return hashlib.sha1(os.path.abspath(doc_path).lower().encode("utf-8")).hexdigest()[:16]

def _dir(doc_path):
    d = os.path.join(_local_root(), _key(doc_path))
    os.makedirs(os.path.join(d, "vault"), exist_ok=True)
    return d

def _legacy_dir(doc_path):
    return os.path.join(os.path.dirname(os.path.abspath(doc_path)), ".caiguard")

def manifest_path(doc_path):
    return os.path.join(_dir(doc_path), os.path.basename(doc_path) + ".cai.json")

def vault_path(doc_path, version):
    return os.path.join(_dir(doc_path), "vault", f"{os.path.basename(doc_path)}.v{version}")

def _migrate_legacy(doc_path):
    """Copy a pre-existing sidecar (next to the doc, e.g. inside OneDrive) into the local store,
    then remove it so it stops syncing. Best-effort; never fatal."""
    src = _legacy_dir(doc_path)
    lm = os.path.join(src, os.path.basename(doc_path) + ".cai.json")
    if not os.path.exists(lm):
        return
    try:
        dst = _dir(doc_path)
        dst_manifest = os.path.join(dst, os.path.basename(doc_path) + ".cai.json")
        shutil.copy2(lm, dst_manifest)
        vault_ok = True
        lv = os.path.join(src, "vault")
        if os.path.isdir(lv):
            for f in os.listdir(lv):
                s_f, d_f = os.path.join(lv, f), os.path.join(dst, "vault", f)
                try:
                    shutil.copy2(s_f, d_f)
                    if not (os.path.exists(d_f) and os.path.getsize(d_f) == os.path.getsize(s_f)):
                        vault_ok = False
                except OSError:
                    vault_ok = False
        # only remove the legacy sidecar once the manifest AND every vault byte-copy are confirmed —
        # otherwise we could delete the only byte vault and make Restore-to-locked impossible.
        if vault_ok and os.path.exists(dst_manifest) and os.path.getsize(dst_manifest) > 0:
            shutil.rmtree(src, ignore_errors=True)
    except Exception:
        pass

def load(doc_path):
    p = manifest_path(doc_path)
    if not os.path.exists(p):
        _migrate_legacy(doc_path)
        if not os.path.exists(p):
            return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except (ValueError, OSError):
        # torn/corrupt manifest — fall back to a good backup if one exists rather than crashing
        bak = p + ".bak"
        if os.path.exists(bak):
            try:
                return json.load(open(bak, encoding="utf-8"))
            except Exception:
                return None
        return None

def save(doc_path, manifest):
    """Atomic manifest write (temp + os.replace) under a lock, keeping a .bak of the prior good copy."""
    p = manifest_path(doc_path)
    if isinstance(manifest.get("history"), list) and len(manifest["history"]) > 400:
        manifest["history"] = manifest["history"][:400]   # keep the manifest from growing unbounded
    with _SAVE_LOCK:
        if os.path.exists(p):
            try: shutil.copy2(p, p + ".bak")
            except OSError: pass
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            f.flush(); os.fsync(f.fileno())
        # Retry the atomic swap: on Windows a scanner/the running app can briefly hold the file
        # (WinError 5 / PermissionError) — a short backoff clears it instead of failing the push.
        import time
        for _i in range(5):
            try:
                os.replace(tmp, p); break
            except PermissionError:
                if _i == 4:
                    raise
                time.sleep(0.3 * (_i + 1))

def snapshot_bytes(doc_path, version):
    shutil.copy2(doc_path, vault_path(doc_path, version))

def now():
    return datetime.datetime.now().isoformat(timespec="seconds")
