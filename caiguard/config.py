"""App-level settings + the list of enrolled documents (stored in %LOCALAPPDATA%\\CAIGuard)."""
import os, json

def cfg_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, "CAIGuard")
    os.makedirs(d, exist_ok=True)
    return d

def _p(name): return os.path.join(cfg_dir(), name)

DEFAULTS = {"ai_provider": "Anthropic (Claude)", "ai_key": "", "ai_model": "claude-3-5-sonnet-latest", "autostart": True, "auto_revert": False}

def _seed_key():
    """Pre-seed the API key from the app-specific env var only.

    Deliberately NOT reading the generic ANTHROPIC_API_KEY: that could silently piggyback an
    unrelated ambient key and cause document text to be sent to a provider without intent.
    Nothing is ever written to disk unless the user explicitly saves."""
    v = os.environ.get("CAIGUARD_API_KEY")
    return v.strip() if v and v.strip() else ""

def load_settings():
    p = _p("settings.json")
    s = dict(DEFAULTS)
    if os.path.exists(p):
        s.update(json.load(open(p, encoding="utf-8")))
    if not s.get("ai_key"):
        s["ai_key"] = _seed_key()          # pre-seed from env when no key is stored yet
    return s

def save_settings(s):
    json.dump(s, open(_p("settings.json"), "w", encoding="utf-8"), indent=2)

# ---- Semantic Library (vocab) + Lexicon persistence ----------------------
def load_vocab():
    from .engine import DEFAULT_VOCAB
    p = _p("vocab.json")
    if os.path.exists(p):
        try:
            saved = json.load(open(p, encoding="utf-8"))
            # Merge over defaults so a category ABSENT from an older saved file (e.g. "conditions")
            # falls back to its default instead of vanishing. A category present-but-empty is
            # respected (that's a deliberate user choice).
            merged = {k: (dict(v) if isinstance(v, dict) else list(v)) for k, v in DEFAULT_VOCAB.items()}
            for k, val in saved.items():
                merged[k] = val
            return merged
        except Exception:
            pass
    return DEFAULT_VOCAB

def save_vocab(v):
    json.dump(v, open(_p("vocab.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)

def reset_vocab():
    p = _p("vocab.json")
    if os.path.exists(p): os.remove(p)

def load_lexicon():
    p = _p("lexicon.json")
    if os.path.exists(p):
        try: return json.load(open(p, encoding="utf-8"))
        except Exception: pass
    return []

def save_lexicon(items):
    json.dump(items, open(_p("lexicon.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)

def load_enrolled():
    p = _p("enrolled.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []

def save_enrolled(lst):
    json.dump(lst, open(_p("enrolled.json"), "w", encoding="utf-8"), indent=2)

def add_enrolled(path):
    path = os.path.abspath(path); lst = load_enrolled()
    if path not in lst: lst.append(path); save_enrolled(lst)

def remove_enrolled(path):
    path = os.path.abspath(path); lst = [x for x in load_enrolled() if x != path]; save_enrolled(lst)
