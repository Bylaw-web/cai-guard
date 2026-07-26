"""Deterministic semantic + structural change engine (no AI, no I/O).

Ported from the validated JS prototype. Pure functions over stdlib only.
"""
import re, hashlib, json, difflib
from collections import Counter

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def align_sequences(base_texts, cur_texts):
    """Align two ordered lists of paragraph texts by CONTENT, not position.

    Returns a list of (base_index, cur_index) pairs in document order, where
    either element may be None:
        (bi, cj)   -> baseline paragraph bi corresponds to current paragraph cj
        (bi, None) -> baseline paragraph was removed
        (None, cj) -> current paragraph was inserted

    This makes a single inserted/deleted paragraph a local event instead of a
    cascade: everything that is byte-identical stays anchored, so edits to
    shifted paragraphs are still diffed against their true prior text.
    """
    sm = difflib.SequenceMatcher(a=base_texts, b=cur_texts, autojunk=False)
    pairs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                pairs.append((i1 + k, j1 + k))
        elif tag == "replace":
            # Pair items in the block by TEXT SIMILARITY, not position, so an edit next to a
            # deletion is attributed to the paragraph it actually descends from (greedy best-match).
            b_idx = list(range(j1, j2))
            used = set()
            for ai in range(i1, i2):
                best, best_r = None, 0.0
                for bj in b_idx:
                    if bj in used:
                        continue
                    r = difflib.SequenceMatcher(None, base_texts[ai], cur_texts[bj]).ratio()
                    if r > best_r:
                        best_r, best = r, bj
                if best is not None and best_r >= 0.5:
                    used.add(best); pairs.append((ai, best))
                else:
                    pairs.append((ai, None))       # baseline item with no good match -> removed
            for bj in b_idx:
                if bj not in used:
                    pairs.append((None, bj))        # current item with no match -> inserted
        elif tag == "delete":
            for k in range(i1, i2):
                pairs.append((k, None))
        elif tag == "insert":
            for k in range(j1, j2):
                pairs.append((None, k))
    return pairs

def t1(s: str) -> str:
    """Normalize whitespace/case — two texts equal under t1 differ only cosmetically."""
    return re.sub(r"\s+", " ", s).strip().lower()

# ---------------------------------------------------------------------------
#  SEMANTIC LIBRARY  (the built-in, user-editable governance vocabulary)
#  Each entry carries a plain-language meaning so it can be shown & edited in
#  Settings ▸ Semantic Library. `modals` also carry an obligation-strength rank
#  (3 strong · 2 middle · 1 weak) so a downgrade registers as a weakened control.
# ---------------------------------------------------------------------------
DEFAULT_VOCAB = {
    "modals": {
        "MUST":        {"rank": 3, "meaning": "Hard obligation — required, no discretion."},
        "SHALL":       {"rank": 3, "meaning": "Hard obligation (legal 'shall')."},
        "WILL":        {"rank": 3, "meaning": "Firm commitment / certainty."},
        "HAS TO":      {"rank": 3, "meaning": "Hard obligation (informal)."},
        "HAVE TO":     {"rank": 3, "meaning": "Hard obligation (informal)."},
        "HAD TO":      {"rank": 3, "meaning": "Past hard obligation."},
        "NEED TO":     {"rank": 3, "meaning": "Necessity / requirement."},
        "NEEDS TO":    {"rank": 3, "meaning": "Necessity / requirement."},
        "REQUIRED TO": {"rank": 3, "meaning": "Explicit requirement."},
        "OBLIGATED TO":{"rank": 3, "meaning": "Explicit obligation."},
        "CANNOT":      {"rank": 3, "meaning": "Hard prohibition."},
        "CAN'T":       {"rank": 3, "meaning": "Hard prohibition (informal)."},
        "SHOULD":      {"rank": 2, "meaning": "Recommendation — expected but not mandatory."},
        "OUGHT TO":    {"rank": 2, "meaning": "Recommendation."},
        "CAN":         {"rank": 2, "meaning": "Ability / plain permission."},
        "ABLE TO":     {"rank": 2, "meaning": "Ability."},
        "WOULD":       {"rank": 2, "meaning": "Conditional commitment."},
        "MAY":         {"rank": 1, "meaning": "Permission / possibility — optional."},
        "MIGHT":       {"rank": 1, "meaning": "Possibility — weak/uncertain."},
        "COULD":       {"rank": 1, "meaning": "Possibility / conditional ability."},
    },
    "negation": {
        "DOES NOT": "Negation.", "DO NOT": "Negation.", "WILL NOT": "Negation of commitment.",
        "CANNOT": "Prohibition.", "NO LONGER": "Negation of continuation.", "NOT": "Negation.",
        "NEVER": "Absolute negation over time.", "WITHOUT": "Absence / exclusion.",
        "PROHIBITED": "Explicit prohibition.", "FORBIDDEN": "Explicit prohibition.",
    },
    "frequency": {
        "ALWAYS": "Every time / 100%.", "NEVER": "No time / 0%.", "RARELY": "Very infrequent.",
        "SELDOM": "Infrequent.", "OFTEN": "Frequent.", "USUALLY": "Most of the time.",
        "SOMETIMES": "Part of the time.", "OCCASIONALLY": "Now and then.", "FREQUENTLY": "Often.",
        "CONSTANTLY": "Continuously.", "ALL": "The entire set.", "EVERY": "Each one, no exception.",
        "EACH": "Every individual one.", "ANY": "One or more, unspecified.", "NONE": "Zero of the set.",
        "NO": "Zero / absence.", "EVERYONE": "All people.", "EVERYTHING": "All things.",
        "NOTHING": "No thing.", "NOBODY": "No person.", "ANYONE": "Any person.",
    },
    "conditions": {
        "EXCEPT": "Carves out an exception.", "UNLESS": "Conditions the rule.",
        "PROVIDED THAT": "Adds a proviso/condition.", "PROVIDED": "Adds a proviso/condition.",
        "NOTWITHSTANDING": "Overrides other provisions.", "SUBJECT TO": "Makes it conditional.",
        "EXCLUDING": "Removes from scope.", "OTHER THAN": "Carves out.", "BUT NOT": "Carves out.",
        "SAVE FOR": "Except for.", "IN THE EVENT": "Adds a condition.", "IF": "Adds a condition.",
    },
    "stance": {
        "REALIZE": "Come to understand (implies it's true).", "ADMIT": "Concede (implies reluctance).",
        "ACKNOWLEDGE": "Formally recognize.", "BELIEVE": "Hold as opinion (not asserted fact).",
        "KNOW": "Assert as known fact.", "THINK": "Opinion.", "ASSUME": "Take as given without proof.",
        "CLAIM": "Assert (contested).", "DENY": "Assert untrue.", "SUGGEST": "Propose tentatively.",
        "ARGUE": "Assert with reasons.", "CONCEDE": "Grant a point.", "ASSERT": "State firmly.",
        "DOUBT": "Regard as unlikely.", "SUSPECT": "Believe likely (negative).",
        "CONTEND": "Assert in dispute.", "RECOGNIZE": "Accept as valid.",
    },
    "roles": {r: "Named party / actor." for r in
        ["MANAGER","DIRECTOR","OFFICER","CFO","CEO","CONTRACTOR","SUBCONTRACTOR","OWNER","ARCHITECT",
         "ENGINEER","SURETY","INSURER","EMPLOYEE","VENDOR","AUDITOR","ADMINISTRATOR","SUPERVISOR",
         "COMMITTEE","BOARD"]},
}

# The LEXICON is the user's own locked-meaning watchlist: terms whose presence carries meaning,
# so swapping one out (even for an ordinary-looking word) is caught as a semantic change.
# Each item: {"term": "...", "meaning": "..."}.  Empty by default.
DEFAULT_LEXICON = []

# Structural value patterns (always on — not part of the editable library).
_MONEY  = re.compile(r"\$[\d,]+(?:\.\d+)?")
_DUR    = re.compile(r"\b\d+\s*(?:days?|weeks?|months?|years?)\b", re.I)
_PCT    = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent)\b", re.I)
_NUM    = re.compile(r"\d[\d,]*(?:\.\d+)?")
_DATE   = re.compile(r"\b(?:19|20)\d{2}\b")

# --- live configuration, (re)built by configure() -------------------------
RANK = {}
_MODAL = _NEG = _FREQ = _STANCE = _ROLE = _COND = _LEX = None
_LEX_TERMS = {}

_NEVER = r"(?!x)x"   # a regex that never matches — used when a category is empty

def _alt(terms):
    """Build a whitespace-flexible, longest-first alternation regex body from a list of phrases."""
    ts = sorted({t.strip().upper() for t in terms if t and t.strip()}, key=len, reverse=True)
    return "|".join(re.escape(t).replace(r"\ ", r"\s+") for t in ts)

def _compile_group(terms):
    """Compile a word-boundary alternation, or a never-match if the category is empty
    (an empty alternation would otherwise match the empty string at every boundary)."""
    body = _alt(terms)
    return re.compile(r"\b(?:" + body + r")\b") if body else re.compile(_NEVER)

def configure(vocab=None, lexicon=None):
    """(Re)compile the engine from a semantic-library vocab dict and a lexicon list.

    Safe to call at import (with defaults) and again whenever the user edits either in Settings.
    """
    global RANK, _MODAL, _NEG, _FREQ, _STANCE, _ROLE, _COND, _LEX, _LEX_TERMS
    v = vocab or DEFAULT_VOCAB
    modals = v.get("modals", {})
    RANK = {k.upper(): (val.get("rank", 0) if isinstance(val, dict) else int(val or 0))
            for k, val in modals.items()}

    # negated modal forms (e.g. "MUST NOT") count as strong; list them first
    bases = [b for b in ["MUST","SHALL","SHOULD","MAY","MIGHT","CAN","COULD","WOULD","WILL"] if b in RANK]
    neg_modals = "|".join(re.escape(b) + r"\s+NOT" for b in bases)
    modal_alt = _alt(modals.keys())
    modal_body = (neg_modals + "|" if neg_modals else "") + modal_alt
    _MODAL = re.compile(r"\b(?:" + modal_body + r")\b") if modal_alt else re.compile(_NEVER)

    _NEG   = _compile_group(v.get("negation", {}))
    _FREQ  = _compile_group(v.get("frequency", {}))
    _ROLE  = _compile_group(v.get("roles", {}))
    _COND  = _compile_group(v.get("conditions", {}))
    # stance verbs: match base form + common inflections
    stance = sorted({s.strip().upper() for s in v.get("stance", {}) if s.strip()}, key=len, reverse=True)
    _STANCE = re.compile(r"\b(?:" + "|".join(re.escape(s) + r"(?:S|ES|ED|D)?" for s in stance) + r")\b") \
              if stance else re.compile(r"(?!x)x")
    # lexicon watchlist
    lex = lexicon if lexicon is not None else DEFAULT_LEXICON
    _LEX_TERMS = {i["term"].strip().upper(): i.get("meaning", "") for i in lex if i.get("term", "").strip()}
    _LEX = re.compile(r"\b(?:" + _alt(_LEX_TERMS.keys()) + r")\b") if _LEX_TERMS else None

def meaning(text: str) -> dict:
    U = text.upper()
    m = {
        "modals":      [re.sub(r"\s+", " ", x) for x in _MODAL.findall(U)] if _MODAL else [],
        "negation":    _NEG.findall(U) if _NEG else [],
        "frequency":   _FREQ.findall(U) if _FREQ else [],
        "conditions":  [re.sub(r"\s+", " ", x) for x in _COND.findall(U)] if _COND else [],
        "stance":      _STANCE.findall(U) if _STANCE else [],
        "money":       _MONEY.findall(text),
        "durations":   [re.sub(r"\s+", " ", x.lower()) for x in _DUR.findall(text)],
        "percentages": [re.sub(r"\s+", "", x.lower()) for x in _PCT.findall(text)],
        "numbers":     [x.replace(",", "") for x in _NUM.findall(text)],
        "roles":       _ROLE.findall(U) if _ROLE else [],
        "dates":       _DATE.findall(text),
        "lexicon":     ([re.sub(r"\s+", " ", x) for x in _LEX.findall(U)] if _LEX else []),
    }
    return m

configure(DEFAULT_VOCAB, DEFAULT_LEXICON)

def semantic_hash(text: str) -> str:
    return sha256(json.dumps(meaning(text), sort_keys=True, ensure_ascii=False))

def content_hash(text: str) -> str:
    return sha256(text)

def _rank(m):
    return RANK.get(m, 3 if "NOT" in m else 0)

def detect_weakening(old_modals, new_modals):
    """A weakening is a strong modal that DISAPPEARED being replaced by a weaker one.

    Uses multiset differences, not positional pairing, so merely *adding* a weaker modal
    elsewhere (e.g. inserting "MAY request an extension" before an untouched "MUST deliver")
    is not mistaken for a downgrade.
    """
    removed = Counter(old_modals) - Counter(new_modals)   # obligations that vanished
    added = Counter(new_modals) - Counter(old_modals)     # obligations that appeared
    if not removed or not added:
        return None
    r_from = max(removed.elements(), key=_rank)
    r_to = min(added.elements(), key=_rank)
    if 0 < _rank(r_to) < _rank(r_from):
        return {"from": r_from, "to": r_to}
    return None

_LABELS = {"modals":"Obligation","money":"Amount","durations":"Duration","percentages":"Percentage",
           "numbers":"Number","roles":"Party","dates":"Date","negation":"Polarity",
           "frequency":"Frequency/Scope","stance":"Stance","conditions":"Condition/Exception","lexicon":"Lexicon"}

def token_diffs(om, nm):
    out = []
    for k, label in _LABELS.items():
        a, b = ", ".join(om.get(k, [])), ", ".join(nm.get(k, []))
        if a != b:
            out.append({"label": label, "old": a or "—", "new": b or "—"})
    return out

def classify_section(old: str, new: str) -> dict:
    """Return {'level': none|cosmetic|structural|semantic, 'weak': ..., 'diffs': [...]}"""
    if old == new:
        return {"level": "none"}
    if t1(old) == t1(new):
        return {"level": "cosmetic"}
    om, nm = meaning(old), meaning(new)
    same = om == nm
    ratio = len(new) / max(1, len(old))
    if same:
        return {"level": "structural" if (ratio < 0.6 or ratio > 1.6) else "cosmetic"}
    return {"level": "semantic", "weak": detect_weakening(om["modals"], nm["modals"]),
            "diffs": token_diffs(om, nm)}

_STOP = set("the a an of to and or in on for with by is are be as at from that this it its their his her our your not no".split())
def _words(t):
    return [w for w in re.findall(r"[a-zA-Z']+", t.lower()) if w not in _STOP]
def advise(old, new):
    """Advisory (not a hard verdict): does a token-cosmetic change still look like it could
    shift meaning or perception? Returns a short reason or None. This is where the AI lane
    plugs in; the deterministic heuristic below runs with no key."""
    if old == new: return None
    ow, nw = _words(old), _words(new)
    so, sn = len(re.findall(r"[.!?]", old)), len(re.findall(r"[.!?]", new))
    changed = len((set(nw) - set(ow)) | (set(ow) - set(nw)))
    if so != sn:   return "sentence structure changed — review the meaning"
    if changed >= 3: return "wording changed substantially — may shift meaning or perception"
    if changed >= 1: return "wording changed — quick review recommended"
    return None
