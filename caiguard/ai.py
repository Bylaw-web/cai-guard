"""Ask AI — a conversational assistant wired to a real model (Anthropic / OpenAI / Ollama).

With a key set it CHATS: it answers questions, discusses the document, and brainstorms, and — only
when you actually want changes — proposes exact edits. With no key it falls back to a small offline
find/replace engine and tells you to connect a key. Either way edits are only *proposed* — you
confirm, and they still go through change review, so the AI can never silently alter the document.
Each proposed edit is bound to its section's predicted hashes (computed here, never trusted to the model).
"""
import re, json, urllib.request
from .engine import classify_section, content_hash, semantic_hash

def _aug(e):
    """Bind each proposed edit to its section's hashes (the newer UI + hashed-apply need these)."""
    e["old_content_hash"] = content_hash(e["old"])[:16]
    e["new_content_hash"] = content_hash(e["new"])[:16]
    e["old_semantic_hash"] = semantic_hash(e["old"])[:8]
    e["new_semantic_hash"] = semantic_hash(e["new"])[:8]
    return e

# ------------------------------------------------------------------ offline
def _ci_replace(text, old, new):
    return re.sub(re.escape(old), lambda m: new, text, flags=re.I)

_QUOTES = "“”‘’«»¨´`"
def _pair(msg):
    qn = msg
    for ch in _QUOTES:
        qn = qn.replace(ch, '"')
    quoted = [q.strip() for q in re.findall(r'"([^"]+)"', qn) if q.strip()]
    if len(quoted) >= 2 and quoted[0].lower() != quoted[1].lower():
        return quoted[0], quoted[1]
    for pat in [
        r'\bchange\s+(?:my\s+|the\s+)?(?:name\s+)?from\s+"?(.+?)"?\s+to\s+"?(.+?)"?\s*$',
        r'\b(?:change|update|edit|set|make)\s+"?(.+?)"?\s+(?:to|into|say|says|read|reads|be)\s+"?(.+?)"?\s*$',
        r'\breplace\s+"?(.+?)"?\s+with\s+"?(.+?)"?\s*$',
        r'\brename\s+"?(.+?)"?\s+to\s+"?(.+?)"?\s*$',
        r'"?(.+?)"?\s*(?:->|=>|→)\s*"?(.+?)"?\s*$',
    ]:
        m = re.search(pat, qn, re.I)
        if m:
            old, new = m.group(1).strip().strip('"'), m.group(2).strip().strip('"')
            if old and old.lower() != new.lower():
                return old, new
    if len(quoted) == 1:
        m = re.search(r'(?:just\s+)?(?:says?|reads?|becomes?|to|be)\s+"?([A-Za-z0-9][\w .\'\-]{0,60})', qn, re.I)
        if m:
            new = m.group(1).strip().rstrip(".")
            if new.lower() != quoted[0].lower():
                return quoted[0], new
    return None

def parse_intent(sections, msg):
    m = msg.lower()
    region = "header" if re.search(r'\bheader\b', m) else ("footer" if re.search(r'\bfooter\b', m) else None)
    scoped = lambda s: (s["region"] == region) if region else (s["region"] == "body")
    edits = []
    pair = _pair(msg)
    if pair:
        old, new = pair
        for s in sections:
            if scoped(s) and old.lower() in s["text"].lower():
                nb = _ci_replace(s["text"], old, new)
                if nb != s["text"]:
                    r = classify_section(s["text"], nb)
                    edits.append({"id": s["id"], "old": s["text"], "new": nb,
                                  "level": "control-weakened" if r.get("weak") else r["level"]})
        if edits: return edits, None
        return [], f'Couldn\'t find "{old}" in the document.'
    money = re.search(r'\$[\d,]+', msg); money = money.group(0) if money else None
    days = re.search(r'(\d+)\s*days?', m); days = days.group(1) if days else None
    strengthen = bool(re.search(r'strengthen|tighten|mandatory|\bmust\b', m))
    weaken = bool(re.search(r'weaken|soften|optional|\bshould\b', m))
    for s in sections:
        if not scoped(s) or len(edits) >= 20: continue
        nb = s["text"]
        if money and re.search(r'\$[\d,]+', nb): nb = re.sub(r'\$[\d,]+', lambda _: money, nb, count=1)
        elif days and re.search(r'\d+\s*days?', nb, re.I): nb = re.sub(r'(\d+)(\s*days?)', lambda mm: days + mm.group(2), nb, count=1, flags=re.I)
        elif strengthen and re.search(r'\bshould\b', nb, re.I): nb = re.sub(r'\bshould\b', "must", nb, count=1, flags=re.I)
        elif weaken and re.search(r'\bmust\b', nb, re.I): nb = re.sub(r'\bmust\b', "should", nb, count=1, flags=re.I)
        if nb != s["text"]:
            r = classify_section(s["text"], nb)
            edits.append({"id": s["id"], "old": s["text"], "new": nb, "level": "control-weakened" if r.get("weak") else r["level"]})
    return edits, None

# ------------------------------------------------------------------ real model
_SYS = ("You are CAI Guard's writing assistant, embedded in a local document-governance app. "
        "Talk naturally and be genuinely helpful — answer questions, discuss the document, brainstorm, explain. "
        "You do NOT edit the document directly; you PROPOSE edits and the user confirms each one. "
        "You are given SECTIONS (a JSON array of {id,text}) and the user's MESSAGE. "
        "Reply with ONLY a single JSON object, no prose outside it and no code fences:\n"
        '{"reply":"<your conversational answer>","edits":[{"id":"<section id>","new":"<full replacement text for that section>"}]}\n'
        "Use an empty edits array when you are only chatting or no change is needed. Only include sections "
        "that must change; give the FULL new text for each; keep everything else identical.")

def _sections_payload(sections):
    return json.dumps([{"id": s["id"], "text": s["text"]} for s in sections][:200], ensure_ascii=False)

def _to_edits(arr, sections):
    byid = {s["id"]: s for s in sections}
    out = []
    for e in arr or []:
        s = byid.get(e.get("id"))
        if not s or "new" not in e or e["new"] == s["text"]: continue
        r = classify_section(s["text"], e["new"])
        out.append({"id": s["id"], "old": s["text"], "new": e["new"],
                    "level": "control-weakened" if r.get("weak") else r["level"]})
    return out

def _extract(txt):
    """Parse the model reply into (reply_text, raw_edits). Prefers a {reply,edits} object;
    tolerates a bare edits array or plain prose."""
    t = (txt or "").strip()
    m = re.search(r'\{.*\}', t, re.S)
    # only treat it as the wrapper object if it actually carries reply/edits keys —
    # otherwise a bare edits array's inner object would be misread as the wrapper.
    if m:
        try:
            o = json.loads(m.group(0))
            if isinstance(o, dict) and ("reply" in o or "edits" in o):
                return (o.get("reply") or ""), (o.get("edits") or [])
        except Exception:
            pass
    a = re.search(r'\[.*\]', t, re.S)
    if a:
        try:
            arr = json.loads(a.group(0))
            if isinstance(arr, list):
                return "", arr
        except Exception:
            pass
    return t, []

def _http(url, headers, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())

def _anthropic(sections, msg, key, model):
    d = _http("https://api.anthropic.com/v1/messages",
              {"content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"},
              {"model": model or "claude-3-5-sonnet-latest", "max_tokens": 4000, "system": _SYS,
               "messages": [{"role": "user", "content": "MESSAGE: " + msg + "\n\nSECTIONS:\n" + _sections_payload(sections)}]})
    return _extract(d["content"][0]["text"])

def _openai(sections, msg, key, model):
    if not model or "claude" in (model or ""): model = "gpt-4o-mini"
    d = _http("https://api.openai.com/v1/chat/completions",
              {"content-type": "application/json", "authorization": "Bearer " + key},
              {"model": model, "temperature": 0.2,
               "messages": [{"role": "system", "content": _SYS},
                            {"role": "user", "content": "MESSAGE: " + msg + "\n\nSECTIONS:\n" + _sections_payload(sections)}]})
    return _extract(d["choices"][0]["message"]["content"])

def _ollama(sections, msg, model):
    d = _http("http://localhost:11434/api/generate", {"content-type": "application/json"},
              {"model": model or "llama3", "stream": False,
               "prompt": _SYS + "\n\nMESSAGE: " + msg + "\n\nSECTIONS:\n" + _sections_payload(sections)})
    return _extract(d.get("response", ""))

def propose(sections, msg, settings):
    settings = settings or {}
    key = (settings.get("ai_key") or "").strip()
    provider = settings.get("ai_provider", "") or ""
    model = settings.get("ai_model") or ""
    engine, note, reply, edits = "offline", None, None, []
    if key or "Ollama" in provider:
        try:
            if "OpenAI" in provider:   reply, raw = _openai(sections, msg, key, model)
            elif "Ollama" in provider: reply, raw = _ollama(sections, msg, model)
            else:                      reply, raw = _anthropic(sections, msg, key, model)
            edits = _to_edits(raw, sections)
            engine = "ai"
            if not reply:
                reply = (f"Proposed {len(edits)} edit(s) below." if edits
                         else "I read the document and don't see a change needed for that.")
        except Exception as ex:
            engine, note = "ai-error", "AI request failed: " + str(ex)[:160]
            reply = note
    else:
        edits, note = parse_intent(sections, msg)
        reply = note or (f"Proposed {len(edits)} edit(s) below — review each." if edits else None)
        if not edits and not note:
            note = ("Connect an AI key in Settings to chat and run full AI on any instruction. "
                    "(Offline mode only does simple find/replace.)")
            reply = note
    for e in edits:
        _aug(e)
    return {"edits": edits, "engine": engine, "note": note, "reply": reply}
