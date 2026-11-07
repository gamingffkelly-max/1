"""Script understanding + scene planning: sentence-level shots, character registry, camera and lighting per shot."""
import re
import writer
from config import SHOT_LONG, SHOT_SHORT

CAMERAS = ["push_in", "pan_right", "pull_out", "tilt_up", "pan_left", "drift", "tilt_down"]
LIGHT_RULES = [("night|dark|midnight|blackout", "night lighting, city lights"), ("sunset|dusk|evening|sunrise", "golden hour light"),
               ("office|room|bank|lab|inside|boardroom|factory", "warm interior lighting"),
               ("crash|crisis|fear|collapse|panic|storm", "dramatic low-key lighting")]
LIGHT_CYCLE = ["soft overcast daylight", "dramatic side lighting", "cool morning light", "golden hour light"]

def characters(plan, short):
    """Recurring characters (fixed look text reused in every shot that shows them)."""
    try:
        d = writer.jask(f"Story: {plan.get('title')} - {plan.get('logline') or str(plan.get('narration', ''))[:400]}\n"
                        f"List 0 to 3 recurring on-screen characters ONLY if people are needed to tell it. "
                        f"JSON: {{\"characters\":[{{\"id\":\"c1\",\"look\":\"role, age, face, hair, clothing in 14 words\"}}]}}")
        cs = [c for c in d.get("characters", []) if isinstance(c, dict) and c.get("id") and c.get("look")]
    except Exception:
        cs = []
    return [{"id": str(c["id"]), "look": " ".join(str(c["look"]).split()[:16])} for c in cs[:3]]

def _sents(t): return [s for s in re.split(r"(?<=[.!?])\s+", t.strip()) if s]

def _group(text, short):
    need = int((SHOT_SHORT if short else SHOT_LONG) * 2.6); groups, cur, n = [], [], 0
    for s in _sents(text):
        cur.append(s); n += len(s.split())
        if n >= need: groups.append(" ".join(cur)); cur, n = [], 0
    if cur:
        if groups and n < need / 3: groups[-1] += " " + " ".join(cur)
        else: groups.append(" ".join(cur))
    return groups or [text]

def _visuals(batch, chars):
    ids = {c["id"] for c in chars}; cl = "; ".join(f"{c['id']}={c['look']}" for c in chars) or "none"
    lines = "\n".join(f"{i + 1}. {g}" for i, g in enumerate(batch)); items = []
    try:
        d = writer.jask(f"Characters: {cl}\nNarration shots:\n{lines}\n\nFor EACH numbered shot describe what the camera shows so the picture "
                        f"explains exactly that narration: concrete place, objects, action (max 20 words). Photoreal 3D film look. "
                        f"No text, logos or real people. List character ids only when that character is on screen.\n"
                        f"JSON: {{\"shots\":[{{\"v\":str,\"c\":[ids]}}]}} with exactly {len(batch)} items in order.")
        items = d.get("shots", [])
    except Exception:
        pass
    out = []
    for k, g in enumerate(batch):
        it = items[k] if k < len(items) and isinstance(items[k], dict) else {}
        v = it.get("v") if isinstance(it.get("v"), str) and it["v"].strip() else " ".join(g.split()[:18])
        out.append((" ".join(v.split()[:22]), [x for x in (it.get("c") or []) if x in ids]))
    return out

def _light(v, i):
    for pat, l in LIGHT_RULES:
        if re.search(pat, v, re.I): return l
    return LIGHT_CYCLE[i % len(LIGHT_CYCLE)]

_n = 0
def plan(text, short, chars):
    """Return shots: narration text, time fraction, image prompt, camera move, light, characters."""
    global _n
    groups = _group(text, short); total = sum(len(g.split()) for g in groups) or 1; shots = []
    look = {c["id"]: c["look"] for c in chars}
    for b in range(0, len(groups), 8):
        batch = groups[b:b + 8]
        for k, (v, cids) in enumerate(_visuals(batch, chars)):
            light = _light(v, _n)
            prompt = f"{v}. {' '.join(look[i] + '.' for i in cids)} {light}".replace("  ", " ")
            shots.append({"text": batch[k], "frac": len(batch[k].split()) / total, "prompt": prompt,
                          "camera": CAMERAS[_n % len(CAMERAS)], "light": light, "chars": cids}); _n += 1
    return shots
