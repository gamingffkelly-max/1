#!/usr/bin/env python3
import os, re, sys, json, math, time, random, hashlib, subprocess, wave, datetime as dt
import numpy as np, requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

T0 = time.time()
KIND = (os.getenv("KIND") or "short").strip().lower()
PUB_HOUR = (os.getenv("PUBLISH_HOUR_BD") or "").strip()
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA = "http://127.0.0.1:11434"
SR = 22050
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
try:
    LONG_TARGET = float(os.getenv("LONG_TARGET_MIN") or 105) * 60
except Exception:
    LONG_TARGET = 6300.0
LONG_TARGET = min(LONG_TARGET, 6900.0)
LONG_MAX = 7000.0
LLM_BUDGET = 135 * 60
STATE = f"state_{KIND}.json"
for _d in ("work", "posts", "out", "voices"):
    os.makedirs(_d, exist_ok=True)

INK, SKIN = (22, 22, 26), (244, 244, 241)
TOP = 60
GX, HX = 350, 930
HOST_VOICE = "en_US-ryan-high"
MALE = ["en_GB-alan-medium", "en_US-joe-medium", "en_US-hfc_male-medium", "en_GB-northern_english_male-medium"]
FEMALE = ["en_US-amy-medium", "en_GB-jenny_dioco-medium", "en_US-lessac-medium", "en_GB-alba-medium", "en_US-hfc_female-medium"]
AREAS = ["self-improvement and discipline", "strategy and long-term thinking", "game theory and human behavior",
         "power dynamics and influence", "negotiation and persuasion", "cognitive biases", "decision making under pressure",
         "motivation and habit psychology", "fear, anxiety and courage", "social psychology and group behavior",
         "emotional intelligence", "body language and first impressions", "confidence and self-image",
         "attraction and charisma", "leadership and authority", "stoic and philosophical psychology",
         "memory, attention and focus", "attachment and relationships", "moral psychology", "dark psychology and manipulation awareness",
         "ambition, status and envy", "resilience and grief", "creativity and flow", "money psychology and risk"]
KINDS = ["hoodie", "suit", "turtleneck", "jacket", "sweater", "tee", "bomber"]
HATS, HAIRS = ["beanie", "cap", "none"], ["short", "messy", "curly", "bald", "long"]
BEARDS, CENTERS = ["none", "stubble", "goatee", "mustache", "full"], ["window", "neon", "posters"]
SIDES, MOODS = ["shelves", "plants", "panels", "lamps", "curtain"], ["calm", "tense", "hopeful", "dark", "curious"]
PALETTE = ["#1f2a44", "#3b2f2f", "#2d4a3e", "#5a1f2b", "#222222", "#4a4e69", "#6b4f3a", "#1b3a4b", "#7a5c2e", "#343a40", "#8d99ae", "#2f3e46"]
ACCENTS = ["#FFC21A", "#FF3B30", "#00D1FF", "#7CFF6B", "#FF7A00", "#C77DFF"]
FORMAT = 'Return JSON: {"lines":[{"s":"H","t":"..."},{"s":"G","t":"...","k":"optional key phrase"}]}'
SYS = ("You write dialogue for a serious, professional English podcast about self-improvement, strategy, psychology, "
       "human behavior and power. Host Alex (s=H) asks short, sharp, hard questions (max 18 words). The guest (s=G) gives deep, "
       "concrete answers using real psychological concepts, well-known historical episodes, famous proverbs, mental models "
       "and thought experiments. Never invent studies, statistics or quotes attributed to real people; mention research only in "
       "general, well-established terms. No greetings filler, no sponsor talk, no links, no stage directions. Output valid JSON only.")

# ================= helpers =================
def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)

def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]

def hexok(c, d):
    c = str(c).strip()
    return c if re.fullmatch(r"#[0-9a-fA-F]{6}", c) else d

def pick(v, opts, d):
    return v if v in opts else d

def clamp(v, a, b, d):
    try:
        return min(b, max(a, float(v)))
    except Exception:
        return d

def dark_hex(h, maxl):
    c = hexrgb(h)
    while lum(c) > maxl:
        c = shade(c, 0.85)
    return "#%02x%02x%02x" % c

def ease_out(x):
    return 1 - (1 - x) ** 3

def ease_back(x):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2

_fc = {}
def font(sz):
    sz = int(max(10, sz))
    if sz not in _fc:
        _fc[sz] = ImageFont.truetype(FONT, sz)
    return _fc[sz]

def fmt_ts(s):
    s = int(s)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"

# ================= local LLM =================
def llm(prompt, system=SYS, js=False, temp=0.8, num=2500):
    body = {"model": MODEL, "prompt": prompt, "system": system, "stream": False, "keep_alive": "6h",
            "options": {"temperature": temp, "num_ctx": 8192, "num_predict": num}}
    if js:
        body["format"] = "json"
    r = requests.post(OLLAMA + "/api/generate", json=body, timeout=3600)
    return r.json()["response"].strip()

def llm_json(prompt, system=SYS, tries=4, temp=0.7, num=2500):
    for _ in range(tries):
        try:
            j = json.loads(llm(prompt, system, True, temp, num))
            if isinstance(j, dict):
                return j
        except Exception:
            pass
    raise RuntimeError("LLM JSON failed")

def fix_text(t):
    t = str(t)
    t = re.sub(r"https?://\S+|www\.\S+", "", t)
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]|\*+", "", t)
    t = t.replace("—", ", ").replace("–", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", t).strip()

def clean(x):
    out = []
    if not isinstance(x, list):
        return out
    for d in x:
        try:
            s = str(d.get("s", "")).strip().upper()[:1]
            t = fix_text(d.get("t", ""))
            k = re.sub(r"[^\w\s'&-]", "", str(d.get("k") or "")).strip()[:26]
            if s in ("H", "G") and len(t.split()) >= 3:
                out.append({"s": s, "t": t, "k": k if (s == "G" and 1 <= len(k.split()) <= 4) else ""})
        except Exception:
            pass
    return out

def tidy(lines):
    out = []
    for l in lines:
        t = l["t"]
        if re.search(r"as an ai|language model|sponsor", t, re.I):
            continue
        if l["s"] == "H" and len(t.split()) > 22:
            sents = re.split(r"(?<=[.?!])\s+", t)
            t = sents[0] if len(sents[0].split()) <= 22 else " ".join(t.split()[:20]) + "?"
        out.append({**l, "t": t})
    return out

def wc(lines):
    return sum(len(l["t"].split()) for l in lines)

def est(lines):
    return wc(lines) / 2.45 + 0.35 * len(lines)

def sim(a, b):
    sa, sb = set(a.lower().split()), set(b.lower().split())
    return len(sa & sb) / max(1, len(sa | sb))

def refine(lines, passes):
    for _ in range(passes):
        try:
            crit = llm("Critique this podcast dialogue. List: invented studies/quotes, shallow or generic parts, repetition, "
                       "host questions longer than 18 words, weak hook. Max 100 words.\n" + json.dumps(lines),
                       "You are a strict editor.", False, 0.3, 400)
            j = llm_json("Rewrite the dialogue fixing every issue. Keep similar length, keep the same format and the key phrases.\nISSUES: "
                         + crit + "\nDIALOGUE: " + json.dumps(lines) + "\n" + FORMAT)
            new = tidy(clean(j.get("lines")))
            if new and 0.8 * wc(lines) <= wc(new) <= 1.25 * wc(lines):
                lines = new
        except Exception:
            pass
    return lines

# ================= state / topic / guest =================
def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"topics": [], "guests": []}

def save_state(s):
    json.dump(s, open(STATE, "w"), indent=1)

def pick_topic(state):
    recent = state["topics"][-120:]
    t, angle = "", ""
    for _ in range(6):
        area = random.choice(AREAS)
        j = llm_json(f"Area: {area}\nAlready covered (never repeat or paraphrase): {json.dumps(recent)}\n"
                     "Propose ONE fresh, specific, intriguing topic for a deep expert conversation that makes viewers want to keep watching. "
                     'JSON: {"topic":"...","angle":"one sentence on the surprising angle"}', temp=1.0)
        t, angle = str(j.get("topic", "")).strip(), str(j.get("angle", ""))
        if t and not any(sim(t, r) > 0.5 for r in recent):
            break
    return t or "The psychology of first impressions", angle

def make_guest(topic, state):
    used = state["guests"][-60:]
    try:
        g = llm_json(f"Invent a FICTIONAL expert guest for a podcast about: {topic}. Not a real person. Avoid these names: {used}.\n"
                     'JSON keys: name, gender ("male" or "female"), age (30-75), role, style (5 words about speaking style).', temp=1.0)
    except Exception:
        g = {}
    g["name"] = re.sub(r"[^\w .'-]", "", str(g.get("name") or "Dr. Sam Reed"))[:40] or "Dr. Sam Reed"
    g["gender"] = "female" if str(g.get("gender", "")).lower().startswith("f") else "male"
    g["age"] = int(clamp(g.get("age"), 30, 75, 45))
    g["role"] = str(g.get("role") or "behavioral psychologist")[:60]
    g["style"] = str(g.get("style") or "calm, precise, thoughtful")[:60]
    g["voice"] = random.choice(FEMALE if g["gender"] == "female" else MALE)
    g["pace_mul"] = random.uniform(0.96, 1.06)
    return g

# ================= scripts =================
def script_short(topic, angle, g):
    j = llm_json(f"Topic: {topic}\nAngle: {angle}\nGuest: {g['name']}, {g['role']}, style: {g['style']}\n"
                 "Write a dialogue of 125-145 words total. First line: Alex asks a hook question under 14 words. 5-6 exchanges. "
                 'Add "k" (a 2-4 word on-screen key phrase) to 2 guest lines. End with a memorable closing line from the guest.\n' + FORMAT)
    lines = tidy(clean(j.get("lines")))
    lines = refine(lines, 2)
    for l in lines:
        l["sec"] = 0
    return lines

def plan_more(topic, angle, have, k=12):
    try:
        j = llm_json(f"Topic: {topic}\nAngle: {angle}\nChapters planned so far: {json.dumps([c['title'] for c in have])}\n"
                     f"Plan {k} NEW chapters that continue and deepen a long expert conversation. Cover: origin stories and historical cases, "
                     "mechanisms, mental models, strategy, power dynamics, common mistakes, counter-intuitive twists, practical protocols, "
                     "case studies of ordinary people, philosophical lenses and proverbs, objections, advanced applications. Each must be distinct. "
                     'JSON: {"chapters":[{"title":"...","idea":"..."}]}', temp=0.9)
    except Exception:
        return []
    out = []
    for c in j.get("chapters", []):
        t, d = fix_text(c.get("title", ""))[:70], fix_text(c.get("idea", ""))[:220]
        if t and d and not any(sim(t, x["title"]) > 0.6 for x in have + out):
            out.append({"title": t, "idea": d})
    return out

def write_chapter(topic, g, ch, idx, covered, tail, first, last):
    extra = ("Open with a gripping hook question from Alex that creates curiosity." if first else
             "This is the FINAL chapter: deliver a memorable closing insight from the guest and a short sign-off from Alex." if last else
             "Continue naturally from the last lines; no greetings, no re-introductions, no recap of earlier chapters.")
    p = (f"Topic: {topic}\nGuest: {g['name']} ({g['role']}; speaking style: {g['style']})\n"
         f"Chapter {idx + 1}: {ch['title']} - {ch['idea']}\n"
         f"Points already covered (do NOT repeat): {json.dumps(covered[-14:])}\nLast lines: {json.dumps(tail)}\n{extra}\n"
         "Write 380-450 words in 9-13 exchanges. Alex asks short hard questions. The guest answers with rich concrete detail: a real "
         "historical episode or thought experiment (general facts only), a mental model, a proverb, a practical step. "
         'Add "k" (2-4 word on-screen key phrase) to 3 guest lines. Also add "gist": one sentence summary of this chapter.\n'
         'Return JSON: {"gist":"...","lines":[{"s":"H","t":"..."},{"s":"G","t":"...","k":"..."}]}')
    return llm_json(p, temp=0.85)

def script_long(topic, angle, g):
    plan = []
    for _ in range(6):
        plan += plan_more(topic, angle, plan, 12)
        if len(plan) >= 36:
            break
    lines, titles, covered, i = [], [], [], 0
    while est(lines) < LONG_TARGET - 240 and time.time() - T0 < LLM_BUDGET:
        if i >= len(plan):
            more = plan_more(topic, angle, plan, 12)
            if not more:
                break
            plan += more
        ch = plan[i]
        i += 1
        sec, gist = None, ""
        for _ in range(3):
            try:
                j = write_chapter(topic, g, ch, len(titles), covered, lines[-4:], not lines, False)
            except Exception:
                continue
            s = tidy(clean(j.get("lines")))
            if wc(s) >= 120:
                sec, gist = s, fix_text(j.get("gist", ""))
            if wc(s) >= 260 and sim(" ".join(l["t"] for l in s), " ".join(l["t"] for l in lines[-40:])) < 0.45:
                break
        if not sec:
            continue
        for l in sec:
            l["sec"] = len(titles)
        lines += sec
        titles.append(ch["title"])
        covered.append(gist or ch["title"])
        print(f"chapter {len(titles)} done, est {est(lines) / 60:.1f} min, elapsed {(time.time() - T0) / 60:.0f} min", flush=True)
    if lines:
        try:
            j = write_chapter(topic, g, {"title": "Final insights", "idea": "bring everything together with the most important takeaways"},
                              len(titles), covered, lines[-4:], False, True)
            sec = tidy(clean(j.get("lines")))
            if sec:
                for l in sec:
                    l["sec"] = len(titles)
                lines += sec
                titles.append("Final insights")
        except Exception:
            pass
    return lines, titles

# ================= edit director =================
def rand_edit():
    r = random
    return dict(mood=r.choice(MOODS), cut_rate=r.choice(["fast", "medium", "medium", "slow"]),
                caption_pos=r.choice(["bottom", "mid"]), gesture=r.uniform(0.55, 1.0), caption_size=r.randint(40, 52),
                pace=r.uniform(0.95, 1.04), caption_color="#FFFFFF", accent=r.choice(ACCENTS),
                wall=r.choice(PALETTE), wall2=r.choice(PALETTE), studio_accent=r.choice(ACCENTS),
                desk=r.choice(["#5b3a29", "#2b2b2e", "#6d5846", "#3a2a20", "#1f2f3a"]),
                center=r.choice(CENTERS), sides=r.sample(SIDES, 2),
                host_kind=r.choice(KINDS), host_color=r.choice(PALETTE), host_accent=r.choice(["#ffffff", "#d9d9d9", "#c9ada7", "#9db4c0"]),
                host_hat=r.choice(["beanie", "beanie", "cap", "none"]),
                host_hat_color=r.choice(["#111111", "#2b2d42", "#4a4e69", "#1b4332", "#5c1a1b"]),
                guest_kind=r.choice(KINDS), guest_color=r.choice(PALETTE), guest_accent=r.choice(["#ffffff", "#d9d9d9", "#e0c9a6", "#a9c0d0"]),
                guest_hat=r.choice(["none", "none", "none", "cap", "beanie"]),
                guest_hat_color=r.choice(["#111111", "#2b2d42", "#4a4e69", "#1b4332", "#5c1a1b"]),
                guest_hair=r.choice(HAIRS), guest_hair_color=r.choice(["#1c1816", "#3b2a1e", "#6b4a2b", "#b08d57", "#8a8a8a"]),
                guest_beard=r.choice(BEARDS), guest_glasses=r.random() < 0.4)

def make_edit(topic, g, lines):
    e = rand_edit()
    ex = " ".join(l["t"] for l in lines)[:800]
    try:
        j = llm_json(f"You are a video editing director. Topic: {topic}. Excerpt: {ex}\n"
                     "Design a distinctive look for this episode. JSON keys: "
                     f'mood ({"|".join(MOODS)}), cut_rate (fast|medium|slow), caption_pos (bottom|mid), gesture (0.4-1.0), caption_size (38-54), '
                     "pace (0.95-1.05), accent (hex), wall (hex dark), wall2 (hex dark), studio_accent (hex), desk (hex), "
                     f'center ({"|".join(CENTERS)}), sides (2 of {SIDES}), host_kind, guest_kind (each of {KINDS}), host_color, host_accent, '
                     f'guest_color, guest_accent (hex), host_hat (beanie|cap|none), guest_hat (beanie|cap|none), host_hat_color, guest_hat_color (hex), '
                     f'guest_hair ({"|".join(HAIRS)}), guest_hair_color (hex), guest_beard ({"|".join(BEARDS)}), guest_glasses (true|false).',
                     temp=1.0, tries=3)
    except Exception:
        j = {}
    for k in ("accent", "wall", "wall2", "studio_accent", "desk", "host_color", "host_accent", "guest_color", "guest_accent",
              "host_hat_color", "guest_hat_color", "guest_hair_color"):
        e[k] = hexok(j.get(k), e[k])
    for k, o in (("mood", MOODS), ("cut_rate", ["fast", "medium", "slow"]), ("caption_pos", ["bottom", "mid"]), ("center", CENTERS),
                 ("host_kind", KINDS), ("guest_kind", KINDS), ("host_hat", HATS), ("guest_hat", HATS), ("guest_hair", HAIRS),
                 ("guest_beard", BEARDS)):
        e[k] = pick(j.get(k), o, e[k])
    sd = j.get("sides")
    if isinstance(sd, list) and len(sd) >= 1 and all(s in SIDES for s in sd[:2]):
        e["sides"] = sd[:2]
    e["gesture"] = clamp(j.get("gesture"), 0.4, 1.0, e["gesture"])
    e["caption_size"] = int(clamp(j.get("caption_size"), 38, 54, e["caption_size"]))
    e["pace"] = clamp(j.get("pace"), 0.95, 1.05, e["pace"])
    if isinstance(j.get("guest_glasses"), bool):
        e["guest_glasses"] = j["guest_glasses"]
    e["wall"], e["wall2"] = dark_hex(e["wall"], 95), dark_hex(e["wall2"], 80)
    e["desk"] = dark_hex(e["desk"], 110)
    if g["gender"] == "female":
        e["guest_beard"] = "none"
        e["guest_hair"] = random.choice(["long", "long", "short", "curly"])
    if g["age"] > 58:
        e["guest_hair_color"] = "#b8b8b8"
    if e["guest_hat"] != "none":
        e["guest_hair"] = "short"
    return e

# ================= SEO =================
def make_meta(topic, lines, short, chapters):
    ex = " ".join(l["t"] for l in lines)[:1800]
    try:
        o = llm_json(f"Topic: {topic}\nTranscript excerpt: {ex}\nWrite 6 distinct YouTube title options for an English podcast episode about "
                     "self-improvement, psychology, strategy and human behavior. Rules: max 60 characters, main keyword in the first 3 words, "
                     "strong curiosity or clear benefit, honest, no channel name, no real people, no emojis. "
                     'JSON: {"titles":["..."]}', temp=0.9)
        ts = [re.sub(r"[<>\"]", "", fix_text(t))[:60] for t in o.get("titles", []) if str(t).strip()]
    except Exception:
        ts = []
    ts = ts or [topic[:60]]
    best = ts[0]
    if len(ts) > 1:
        try:
            r = llm_json("Pick the single best title for search and click-through (clear keyword, curiosity, honest). "
                         'Return JSON {"best": index starting at 0}.\n' + json.dumps(ts), temp=0.2, tries=2)
            best = ts[int(r.get("best", 0)) % len(ts)]
        except Exception:
            pass
    try:
        d = llm_json(f"Topic: {topic}\nTitle: {best}\nTranscript excerpt: {ex}\nCreate YouTube SEO metadata. JSON keys: "
                     "summary (90-130 words, main keywords in the first two sentences, no links, no sources, no real people's names), "
                     "takeaways (5 short strings), tags (15 strings, no #, max 30 chars each), hashtags (3 single words), "
                     "thumb_text (two lines separated by '|', ALL CAPS, max 3 words each, curiosity driven).", temp=0.7)
    except Exception:
        d = {}
    summ = re.sub(r"https?://\S+|www\.\S+", "", str(d.get("summary", topic))).strip()
    tk = [fix_text(x) for x in (d.get("takeaways") or [])][:5]
    desc = summ + "\n\n"
    if tk:
        desc += "In this episode:\n" + "\n".join("- " + x for x in tk) + "\n\n"
    if chapters:
        desc += "Chapters:\n" + "\n".join(f"{fmt_ts(a)} {t}" for a, t in chapters) + "\n\n"
    hs = ["#" + re.sub(r"\W", "", str(h)) for h in (d.get("hashtags") or ["psychology", "selfimprovement", "mindset"])[:3]]
    desc += " ".join(hs) + "\n\nThis is an AI-generated fictional conversation with animated characters, made for education and inspiration."
    tags, tot = [], 0
    for t in (d.get("tags") or ["psychology", "self improvement"]):
        t = re.sub(r"[<>#]", "", str(t))[:30].strip()
        if t and tot + len(t) < 440:
            tags.append(t)
            tot += len(t) + 1
    title = best
    if short:
        title = title[:50] + " #Shorts"
        desc += "\n#Shorts"
    th = str(d.get("thumb_text") or "WATCH THIS|NOW")
    return {"title": title, "description": desc[:4800], "tags": tags or ["psychology"], "thumb": th}

# ================= drawing toolkit =================
def chaikin(pts, n=2):
    for _ in range(n):
        out = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            out += [(0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]), (0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1])]
        pts = out
    return pts

def chaikin_open(pts, n=2):
    for _ in range(n):
        out = [pts[0]]
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            out += [(0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]), (0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1])]
        out.append(pts[-1])
        pts = out
    return pts

class P:
    def __init__(self, img, ss, ox=0.0, oy=0.0):
        self.im, self.ss, self.ox, self.oy = img, ss, ox, oy
        self.d = ImageDraw.Draw(img)

    def _t(self, pts):
        return [((x + self.ox) * self.ss, (y + self.oy) * self.ss) for x, y in pts]

    def poly(self, pts, fill=None, ol=None, w=2.0, smooth=0):
        if smooth:
            pts = chaikin(pts, smooth)
        q = self._t(pts)
        if fill is not None:
            self.d.polygon(q, fill=fill)
        if ol is not None:
            self.d.line(q + [q[0]], fill=ol, width=max(1, int(w * self.ss)), joint="curve")

    def line(self, pts, fill, w=2.0, smooth=0):
        if smooth:
            pts = chaikin_open(pts, smooth)
        self.d.line(self._t(pts), fill=fill, width=max(1, int(w * self.ss)), joint="curve")

    def ell(self, x, y, rx, ry, fill=None, ol=None, w=2.0):
        (cx, cy), = self._t([(x, y)])
        s = self.ss
        if ol is not None:
            self.d.ellipse([cx - rx * s, cy - ry * s, cx + rx * s, cy + ry * s], fill=fill, outline=ol, width=max(1, int(w * s)))
        else:
            self.d.ellipse([cx - rx * s, cy - ry * s, cx + rx * s, cy + ry * s], fill=fill)

    def limb(self, pts, w, fill, ol=None, olw=2.5):
        if ol is not None:
            self.line(pts, ol, w + 2 * olw)
            for q in (pts[0], pts[-1]):
                self.ell(q[0], q[1], w / 2 + olw, w / 2 + olw, fill=ol)
        self.line(pts, fill, w)
        for q in (pts[0], pts[-1]):
            self.ell(q[0], q[1], w / 2, w / 2, fill=fill)

# ---------- faces ----------
HOST_FACE = dict(fw=62, ch=82, fh=88, eg=29, erx=16, ery=10, bag=1.0, brow=2.0, nose=31, smile=2.2, droop=0.40, wr=1.0)

def rand_face(seed):
    r = random.Random(seed)
    while True:
        f = dict(fw=r.uniform(54, 70), ch=r.uniform(70, 92), fh=r.uniform(80, 96), eg=r.uniform(24, 35), erx=r.uniform(13, 19),
                 ery=r.uniform(8, 12.5), bag=r.uniform(0.3, 1.4), brow=r.uniform(-3, 5), nose=r.uniform(22, 40),
                 smile=r.uniform(-1.5, 4.5), droop=r.uniform(0.2, 0.55), wr=r.uniform(0.3, 1.5))
        if abs(f["fw"] - 62) > 4 or abs(f["nose"] - 31) > 5 or abs(f["eg"] - 29) > 3:
            return f

def hair_top(p, f, style, col):
    fw, fh = f["fw"], f["fh"]
    n, outer, inner = 17, [], []
    for i in range(n):
        th = math.pi * (1 - i / (n - 1))
        k = 1.0 if style != "messy" else (1.0 if i % 2 == 0 else 1.2)
        outer.append((fw * 1.06 * k * math.cos(th), -fh * 1.12 * k * math.sin(th)))
    for i in range(9):
        th = math.pi * i / 8
        inner.append((fw * 0.97 * math.cos(th), -fh * 0.40 - fh * 0.34 * math.sin(th)))
    if style == "curly":
        for q in outer[1:-1]:
            p.ell(q[0], q[1], 13, 13, fill=col, ol=INK, w=1.8)
        p.poly(outer + inner, fill=col)
    else:
        p.poly(outer + inner, fill=col, ol=INK, w=2.2, smooth=0 if style == "messy" else 1)

def draw_hat(p, f, look):
    fw, fh = f["fw"], f["fh"]
    col = hexrgb(look["hat_color"])
    band = (88, 88, 96) if lum(col) < 90 else shade(col, 0.72)
    dome_h = 1.36 if look["hat"] == "beanie" else 1.22
    dome = [(-fw * 1.06, -fh * 0.5), (-fw * 1.0, -fh * 0.95), (-fw * 0.55, -fh * (dome_h - 0.08)), (0, -fh * dome_h),
            (fw * 0.55, -fh * (dome_h - 0.08)), (fw * 1.0, -fh * 0.95), (fw * 1.06, -fh * 0.5)]
    p.poly(dome, fill=col, ol=INK, w=2.8, smooth=2)
    if look["hat"] == "beanie":
        p.poly([(-fw * 1.08, -fh * 0.64), (fw * 1.08, -fh * 0.64), (fw * 1.06, -fh * 0.46), (-fw * 1.06, -fh * 0.46)],
               fill=band, ol=INK, w=2.6, smooth=1)
        for x in range(-int(fw), int(fw) + 1, 12):
            p.line([(x, -fh * 0.63), (x, -fh * 0.47)], shade(band, 0.7), 1.4)
    else:
        p.poly([(-fw * 1.18, -fh * 0.5), (fw * 1.18, -fh * 0.5), (fw * 1.1, -fh * 0.36), (-fw * 1.1, -fh * 0.36)],
               fill=shade(col, 0.8), ol=INK, w=2.6, smooth=2)

def build_head(f, look, ss):
    img = Image.new("RGBA", (int(300 * ss), int(340 * ss)), (0, 0, 0, 0))
    p = P(img, ss, 150, 160)
    fw, ch, fh = f["fw"], f["ch"], f["fh"]
    hair = hexrgb(look["hair_color"])
    if look["hair"] == "long":
        p.poly([(-fw * 1.12, -fh * 0.55), (-fw * 1.3, 50), (-fw * 1.25, 150), (-fw * 0.4, 168), (fw * 0.4, 168), (fw * 1.25, 150),
                (fw * 1.3, 50), (fw * 1.12, -fh * 0.55)], fill=hair, ol=INK, w=2.4, smooth=2)
    for sg in (-1, 1):
        p.ell(sg * fw * 0.99, 6, 8, 15, fill=SKIN, ol=INK, w=2.2)
    right = [(0, -fh), (fw * 0.55, -fh + 4), (fw * 0.88, -fh * 0.62), (fw * 1.0, -fh * 0.25), (fw * 0.93, 10), (fw * 0.84, 32),
             (fw * 0.62, ch * 0.78), (fw * 0.3, ch * 0.96), (0, ch)]
    p.poly(right + [(-x, y) for x, y in reversed(right[1:-1])], fill=SKIN, ol=INK, w=3.0, smooth=2)
    for sg in (-1, 1):
        cx = sg * f["eg"]
        p.line([(cx - f["erx"] * 1.05, f["ery"] - 8), (cx, f["ery"] - 2 + f["bag"] * 3), (cx + f["erx"] * 1.05, f["ery"] - 8)],
               (188, 172, 198), 3 + f["bag"] * 3, smooth=2)
    nz = f["nose"]
    p.line([(-2, -6), (-6, nz * 0.5), (-10, nz * 0.85), (-3, nz), (8, nz * 0.92)], INK, 2.6, smooth=2)
    if f["wr"] > 0.6:
        for sg in (-1, 1):
            p.line([(sg * fw * 0.36, 22), (sg * fw * 0.44, 40), (sg * fw * 0.4, 58)], INK, 1.8, smooth=2)
    if f["wr"] > 0.5:
        for y in (-fh * 0.55, -fh * 0.4):
            p.line([(-24, y + 3), (0, y - 2), (24, y + 3)], INK, 1.6, smooth=2)
    bd = look["beard"]
    if bd == "stubble":
        r = random.Random(7)
        for _ in range(170):
            x, y = r.uniform(-fw * 0.75, fw * 0.75), r.uniform(26, ch * 0.97)
            if abs(x) < fw * (0.95 - (y / ch) * 0.6):
                p.ell(x, y, 0.8, 0.8, fill=(140, 140, 146))
    if bd in ("mustache", "full"):
        p.poly([(-20, 38), (0, 34), (20, 38), (26, 46), (0, 42), (-26, 46)], fill=hair, smooth=1)
    if bd == "goatee":
        p.poly([(-14, 66), (14, 66), (10, ch * 0.98), (0, ch + 3), (-10, ch * 0.98)], fill=hair, smooth=1)
    if bd == "full":
        p.poly([(-fw * 0.95, 5), (-fw * 0.84, 32), (-fw * 0.62, ch * 0.78), (-fw * 0.3, ch * 0.96), (0, ch), (fw * 0.3, ch * 0.96),
                (fw * 0.62, ch * 0.78), (fw * 0.84, 32), (fw * 0.95, 5), (fw * 0.7, 20), (fw * 0.5, 45), (fw * 0.2, 58),
                (-fw * 0.2, 58), (-fw * 0.5, 45), (-fw * 0.7, 20)], fill=hair)
    if look["hat"] != "none":
        draw_hat(p, f, look)
    elif look["hair"] == "bald":
        for sg in (-1, 1):
            p.poly([(sg * fw * 1.0, -fh * 0.1), (sg * fw * 1.02, -fh * 0.5), (sg * fw * 0.88, -fh * 0.45), (sg * fw * 0.9, -fh * 0.05)],
                   fill=hair, ol=INK, w=1.6)
    else:
        hair_top(p, f, look["hair"], hair)
    return img

def draw_eyes(p, f, lid, gaze):
    for sg in (-1, 1):
        cx, cy, rx, ry = sg * f["eg"], -10, f["erx"], f["ery"]
        p.ell(cx, cy, rx, ry, fill=(252, 252, 250), ol=INK, w=1.8)
        if lid < 0.96:
            px, py = cx + gaze * rx * 0.42, cy + 1.2
            p.ell(px, py, 4.8, 4.8, fill=INK)
            p.ell(px - 1.4, py - 1.6, 1.3, 1.3, fill=(255, 255, 255))
        if lid > 0.02:
            yb = cy - ry + 2 * ry * min(lid, 1.0) * 0.98
            dy = 1.6 if lid < 0.96 else 3.2
            p.poly([(cx - rx - 2, cy - ry - 4), (cx + rx + 2, cy - ry - 4), (cx + rx + 2, yb), (cx, yb + dy), (cx - rx - 2, yb)], fill=SKIN)
            p.line([(cx - rx, yb), (cx, yb + dy), (cx + rx, yb)], INK, 2.4, smooth=2)

def draw_glasses(p, f):
    col = (30, 30, 36)
    for sg in (-1, 1):
        cx, w, h = sg * f["eg"], f["erx"] + 7, f["ery"] + 8
        p.poly([(cx - w, -10 - h), (cx + w, -10 - h), (cx + w, -10 + h), (cx - w, -10 + h)], ol=col, w=2.6, smooth=2)
    p.line([(-f["eg"] + f["erx"] + 7, -12), (f["eg"] - f["erx"] - 7, -12)], col, 2.2)

def draw_brows(p, f, raise_, tilt):
    for sg in (-1, 1):
        y = -10 - f["ery"] - 9 - raise_
        inner = (sg * (f["eg"] - f["erx"] * 0.9), y - tilt)
        outer = (sg * (f["eg"] + f["erx"] * 1.0), y + tilt * 0.5)
        mid = ((inner[0] + outer[0]) / 2, min(inner[1], outer[1]) - 2)
        p.line([inner, mid, outer], (40, 36, 34), 3.4, smooth=2)

def draw_mouth(p, f, v, sm):
    my = f["ch"] * 0.62
    dark, tongue = (58, 26, 34), (226, 140, 150)
    if v == 0:
        p.line([(-14, my - sm * 0.3), (0, my + sm * 0.8), (14, my - sm * 0.3)], INK, 2.6, smooth=2)
    elif v == 1:
        p.ell(0, my, 11, 4.5, fill=dark, ol=INK, w=2)
    elif v == 2:
        p.ell(0, my, 14, 8, fill=dark, ol=INK, w=2)
        p.ell(0, my + 4, 8, 3.2, fill=tongue)
    elif v == 3:
        p.ell(0, my + 1, 16, 13, fill=dark, ol=INK, w=2)
        p.ell(0, my + 7, 10, 5, fill=tongue)
    elif v == 4:
        p.ell(0, my, 8, 9, fill=dark, ol=INK, w=2)
    else:
        p.ell(0, my, 19, 5.5, fill=dark, ol=INK, w=2)
        p.poly([(-15, my - 3.5), (15, my - 3.5), (13, my - 0.5), (-13, my - 0.5)], fill=(250, 250, 248))

# ---------- bodies / arms ----------
def build_body(o, ss):
    img = Image.new("RGBA", (int(460 * ss), int(620 * ss)), (0, 0, 0, 0))
    p = P(img, ss, 0, TOP)
    c, a = hexrgb(o["color"]), hexrgb(o["accent"])
    dk, k = shade(c, 0.72), o["kind"]
    if k == "hoodie":
        p.ell(230, 262, 112, 58, fill=dk, ol=INK, w=2.8)
    p.poly([(58, 560), (54, 350), (76, 306), (150, 276), (230, 268), (310, 276), (384, 306), (406, 350), (402, 560)],
           fill=c, ol=INK, w=3, smooth=1)
    p.poly([(203, 222), (257, 222), (266, 292), (194, 292)], fill=SKIN, ol=INK, w=2.4)
    p.line([(212, 262), (219, 284)], INK, 1.8)
    p.line([(248, 262), (241, 284)], INK, 1.8)
    if k == "hoodie":
        p.poly([(194, 288), (266, 288), (230, 360)], fill=(120, 120, 128), ol=INK, w=2.2)
        p.line([(190, 274), (172, 330), (196, 380)], INK, 3.2, smooth=2)
        p.line([(270, 274), (288, 330), (264, 380)], INK, 3.2, smooth=2)
        p.line([(206, 322), (202, 402)], (170, 170, 176), 2.6)
        p.line([(254, 322), (258, 402)], (170, 170, 176), 2.6)
    elif k == "suit":
        p.poly([(204, 288), (256, 288), (230, 372)], fill=(245, 245, 245), ol=INK, w=2)
        p.poly([(198, 284), (232, 372), (178, 392), (146, 304)], fill=shade(c, 0.86), ol=INK, w=2.4, smooth=1)
        p.poly([(262, 284), (228, 372), (282, 392), (314, 304)], fill=shade(c, 0.86), ol=INK, w=2.4, smooth=1)
        p.poly([(224, 300), (236, 300), (244, 372), (230, 404), (216, 372)], fill=a, ol=INK, w=2)
        p.poly([(222, 292), (238, 292), (236, 306), (224, 306)], fill=shade(a, 0.8), ol=INK, w=1.8)
    elif k == "turtleneck":
        p.poly([(193, 228), (267, 228), (274, 296), (186, 296)], fill=c, ol=INK, w=2.6, smooth=1)
        for y in (244, 258, 272, 286):
            p.line([(194, y), (266, y)], shade(c, 0.6), 1.6)
    elif k == "jacket":
        p.poly([(198, 286), (262, 286), (230, 350)], fill=a, ol=INK, w=2.2)
        p.line([(198, 284), (168, 376)], INK, 3, smooth=1)
        p.line([(262, 284), (292, 376)], INK, 3, smooth=1)
        p.line([(230, 350), (230, 560)], INK, 2.4)
    elif k == "sweater":
        p.ell(230, 288, 46, 15, fill=shade(c, 0.85), ol=INK, w=2.6)
        p.ell(230, 284, 32, 9, fill=SKIN, ol=INK, w=2)
        p.line([(60, 356), (400, 356)], a, 7)
    elif k == "tee":
        p.ell(230, 288, 42, 15, fill=shade(c, 0.8), ol=INK, w=2.6)
        p.ell(230, 285, 30, 8, fill=SKIN, ol=INK, w=2)
    else:
        p.poly([(184, 276), (276, 276), (282, 300), (178, 300)], fill=a, ol=INK, w=2.6, smooth=1)
        p.line([(230, 300), (230, 560)], INK, 2.8)
    return img

def ik(s, h, l1=135, l2=130):
    dx, dy = h[0] - s[0], h[1] - s[1]
    dist = math.hypot(dx, dy) or 1e-3
    d = min(max(dist, abs(l1 - l2) + 2), l1 + l2 - 2)
    ux, uy = dx / dist, dy / dist
    hand = (s[0] + ux * d, s[1] + uy * d)
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    hh = math.sqrt(max(l1 * l1 - a * a, 0))
    mx, my = s[0] + ux * a, s[1] + uy * a
    c1, c2 = (mx - uy * hh, my + ux * hh), (mx + uy * hh, my - ux * hh)
    return (c1 if c1[1] > c2[1] else c2), hand

def draw_hand(p, el, hd, style):
    dx, dy = hd[0] - el[0], hd[1] - el[1]
    n = math.hypot(dx, dy) or 1
    ux, uy, px, py = dx / n, dy / n, -dy / n, dx / n
    c = (hd[0] + ux * 10, hd[1] + uy * 10)
    p.ell(c[0], c[1], 17, 19, fill=SKIN, ol=INK, w=2.4)
    p.limb([(c[0] + px * 13, c[1] + py * 13), (c[0] + px * 19 + ux * 9, c[1] + py * 19 + uy * 9)], 8, SKIN, INK, 1.8)
    if style in ("open", "relax", "point"):
        for i in (-1.5, -0.5, 0.5, 1.5):
            ln = {"open": 20, "relax": 9, "point": 5}[style]
            if style == "point" and i == -1.5:
                ln = 34
            a = (c[0] + ux * 12 + px * i * 8, c[1] + uy * 12 + py * i * 8)
            b = (a[0] + ux * (ln - abs(i) * 3), a[1] + uy * (ln - abs(i) * 3))
            p.limb([a, b], 7.5, SKIN, INK, 1.8)
    else:
        for i in (-1, 0, 1):
            a = (c[0] + ux * 8 + px * i * 8, c[1] + uy * 8 + py * i * 8)
            p.line([a, (a[0] + ux * 5, a[1] + uy * 5)], INK, 1.6)

class Char:
    def __init__(self, face, outfit, look, u):
        self.face, self.outfit, self.look, self.ss = face, outfit, look, 2 * u
        self.body = build_body(outfit, self.ss)
        self.head0 = build_head(face, look, self.ss)

    def render(self, st):
        ss, f = self.ss, self.face
        im = self.body.copy()
        h = self.head0.copy()
        p = P(h, ss, 150, 160)
        draw_eyes(p, f, st["lid"], st["gaze"])
        if self.look["glasses"]:
            draw_glasses(p, f)
        draw_brows(p, f, st["brow"], st["tilt_brow"])
        draw_mouth(p, f, st["mouth"], st["smile"])
        if abs(st["tilt"]) > 0.05:
            h = h.rotate(st["tilt"], resample=Image.BICUBIC, center=(150 * ss, 255 * ss))
        im.alpha_composite(h, dest=(max(0, int((80 + st["bx"]) * ss)), max(0, int((-8 + TOP + st["by"]) * ss))))
        pa = P(im, ss, 0, TOP)
        col = hexrgb(self.outfit["color"])
        fore = SKIN if self.outfit["kind"] == "tee" else col
        for key, root in (("L", (96, 332)), ("R", (364, 332))):
            x, y, sty = st[key]
            el, hd = ik(root, (x, y))
            pa.limb([root, el], 50, col, INK, 2.6)
            pa.limb([el, hd], 42, fore, INK, 2.6)
            draw_hand(pa, el, hd, sty)
        return im.reduce(2)

def base_state(f):
    return {"mouth": 0, "smile": f["smile"], "lid": f["droop"], "gaze": 0.8, "brow": 0.0, "tilt_brow": f["brow"], "tilt": 0.0,
            "bx": 0.0, "by": 0.0, "L": (130, 425, "relax"), "R": (330, 425, "relax")}

# ---------- gestures / controller ----------
SPEAK_G = [((120, 335, "open"), (340, 335, "open")), ((70, 300, "open"), (390, 300, "open")),
           ((130, 425, "relax"), (330, 262, "point")), ((130, 262, "point"), (330, 425, "relax")),
           ((150, 300, "point"), (310, 300, "point")), ((120, 425, "relax"), (320, 285, "fist")),
           ((190, 335, "open"), (270, 335, "open")), ((150, 372, "fist"), (310, 372, "fist"))]
REST = ((130, 425, "relax"), (330, 425, "relax"))
SMALL = ((170, 372, "relax"), (290, 372, "relax"))
THINK_R = ((130, 425, "relax"), (264, 252, "relax"))
THINK_L = ((196, 252, "relax"), (330, 425, "relax"))

class Ctl:
    def __init__(self, k, face, rng, gi):
        self.k, self.face, self.r, self.gi = k, face, rng, gi
        self.pos = {"L": [130.0, 425.0], "R": [330.0, 425.0]}
        self.tg = {"L": [130, 425], "R": [330, 425]}
        self.sty = {"L": "relax", "R": "relax"}
        self.g_next, self.g_last = 0.0, -9.0
        self.blink_t, self.blink_f = rng.uniform(1, 4), -1
        self.gaze_t, self.gz, self.gt = 0.0, 0.8, 1.0
        self.nod, self.brow = 0.0, 0.0
        self.ph = rng.uniform(0, 6.28)

    def set_g(self, g):
        for i, h in enumerate("LR"):
            self.tg[h] = [g[i][0], g[i][1]]
            self.sty[h] = g[i][2]

    def step(self, t, FPS, spk, emph, vis):
        r, dt = self.r, 1.0 / FPS
        me = spk == self.k
        other = spk is not None and not me
        if me:
            if (emph and t - self.g_last > 0.55) or t >= self.g_next:
                self.g_last = t
                self.set_g(r.choice(SPEAK_G) if r.random() < 0.25 + 0.75 * self.gi else REST)
                self.g_next = t + r.uniform(1.1, 2.6)
        elif t >= self.g_next:
            x = r.random()
            self.set_g(THINK_R if x < 0.14 else THINK_L if x < 0.24 else SMALL if x < 0.34 else REST)
            self.g_next = t + r.uniform(2.5, 5.5)
        kk = 1 - math.exp(-(9.0 if me else 5.0) * dt)
        for h in "LR":
            q = self.pos[h]
            q[0] += (self.tg[h][0] - q[0]) * kk
            q[1] += (self.tg[h][1] - q[1]) * kk
        if me and emph:
            self.nod, self.brow = 1.0, 6.0
        elif other and emph and r.random() < 0.3:
            self.nod, self.brow = 0.7, 3.0
        self.nod *= math.exp(-5 * dt)
        self.brow *= math.exp(-4 * dt)
        blink = 0.0
        if self.blink_f < 0 and t >= self.blink_t:
            self.blink_f = 0
        if self.blink_f >= 0:
            nb = max(3, int(0.22 * FPS))
            blink = math.sin(math.pi * (self.blink_f + 0.5) / nb)
            self.blink_f += 1
            if self.blink_f >= nb:
                self.blink_f, self.blink_t = -1, t + r.uniform(2.0, 5.5)
        base = self.face["droop"] * (0.8 if me else 1.0) * (0.5 if self.brow > 3.5 else 1.0)
        lid = base + (1 - base) * min(1.0, blink * 1.15)
        if t >= self.gaze_t:
            self.gt = r.choice([1, 1, 1, 0.25, -0.2]) if me else r.choice([1, 1, 1, 1, 0.3])
            self.gaze_t = t + r.uniform(1.5, 3.5)
        self.gz += (self.gt - self.gz) * 0.3
        side = 1.0 if self.k == "G" else -1.0
        ph = self.ph
        L = (self.pos["L"][0] + 3 * math.sin(2 * math.pi * 0.7 * t + ph), self.pos["L"][1] + 2.5 * math.sin(2 * math.pi * 0.5 * t + ph * 2), self.sty["L"])
        R = (self.pos["R"][0] + 3 * math.sin(2 * math.pi * 0.6 * t + ph * 3), self.pos["R"][1] + 2.5 * math.sin(2 * math.pi * 0.45 * t + ph), self.sty["R"])
        f = self.face
        return {"mouth": vis if me else 0, "smile": f["smile"] + (1.2 + math.sin(t * 0.7 + ph) if other else 0),
                "lid": lid, "gaze": self.gz * side, "brow": self.brow, "tilt_brow": f["brow"],
                "tilt": 1.4 * math.sin(2 * math.pi * 0.09 * t + ph * 1.3) + 0.8 * self.nod,
                "bx": 1.6 * math.sin(2 * math.pi * 0.11 * t + ph),
                "by": 1.4 * math.sin(2 * math.pi * 0.27 * t + ph) + 3.0 * self.nod, "L": L, "R": R}

# ================= studio =================
def lerp(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))

def build_studio(e, u):
    rng = random.Random(random.randint(1, 10 ** 9))
    SW, SH = int(1280 * u), int(720 * u)
    top, bot = np.array(hexrgb(e["wall"]), np.float32), np.array(hexrgb(e["wall2"]), np.float32)
    t = np.linspace(0, 1, SH, dtype=np.float32)[:, None, None]
    arr = np.broadcast_to(top * (1 - t) + bot * t, (SH, SW, 3))
    base = Image.fromarray(np.ascontiguousarray(arr).astype(np.uint8))
    big = base.resize((int(1280 * 2 * u), int(720 * 2 * u)))
    p = P(big, 2 * u)
    glow = Image.new("RGBA", big.size, (0, 0, 0, 0))
    pg = P(glow, 2 * u)
    wallc, acc = hexrgb(e["wall"]), hexrgb(e["studio_accent"])
    book = [(150, 60, 60), (60, 90, 140), (200, 170, 80), (70, 120, 90), (130, 90, 150), (210, 210, 200), (180, 100, 50)]

    def window():
        sky = rng.choice([(255, 150, 90), (70, 90, 160), (20, 25, 60), (120, 170, 220), (250, 190, 120)])
        x0, y0, x1, y1 = 500, 60, 780, 350
        for i in range(30):
            y = y0 + (y1 - y0) * i / 30
            p.poly([(x0, y), (x1, y), (x1, y + (y1 - y0) / 30 + 1), (x0, y + (y1 - y0) / 30 + 1)], fill=lerp(sky, shade(sky, 1.5), i / 30))
        x = x0
        while x < x1:
            w, h = rng.randint(24, 50), rng.randint(40, 150)
            xe = min(x + w, x1)
            p.poly([(x, y1), (x, y1 - h), (xe, y1 - h), (xe, y1)], fill=shade(sky, 0.3))
            for _ in range(5):
                wx, wy = rng.uniform(x + 3, max(x + 4, xe - 6)), rng.uniform(y1 - h + 4, y1 - 8)
                p.poly([(wx, wy), (wx + 4, wy), (wx + 4, wy + 5), (wx, wy + 5)], fill=(255, 220, 130))
            x += w
        p.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], ol=shade(wallc, 0.5), w=8)
        p.line([(640, y0), (640, y1)], shade(wallc, 0.5), 5)

    def neon():
        pts = [(640 + 70 * math.cos(a / 32 * 2 * math.pi), 150 + 70 * math.sin(a / 32 * 2 * math.pi)) for a in range(33)]
        pg.line(pts, acc + (230,), 16)
        pg.line([(560, 270), (720, 270)], acc + (230,), 14)
        p.line(pts, shade(acc, 1.2) if max(acc) < 210 else acc, 6)
        p.line([(560, 270), (720, 270)], acc, 5)

    def posters():
        for x0 in (505, 600, 695):
            y0 = 90
            p.poly([(x0, y0), (x0 + 80, y0), (x0 + 80, y0 + 110), (x0, y0 + 110)], fill=shade(wallc, 1.5), ol=INK, w=3)
            c1 = rng.choice(PALETTE)
            p.ell(x0 + 40, y0 + 45, 22, 22, fill=hexrgb(c1))
            p.poly([(x0 + 10, y0 + 100), (x0 + 40, y0 + 70), (x0 + 70, y0 + 100)], fill=acc)

    def shelves(x0, x1):
        for yy in (150, 255, 360):
            p.poly([(x0, yy), (x1, yy), (x1, yy + 8), (x0, yy + 8)], fill=shade(wallc, 0.45), ol=INK, w=1.5)
            x = x0 + 6
            while x < x1 - 14:
                w, h = rng.randint(8, 16), rng.randint(30, 70)
                p.poly([(x, yy), (x, yy - h), (x + w, yy - h), (x + w, yy)], fill=rng.choice(book), ol=(20, 20, 25), w=1)
                x += w + rng.randint(0, 3)

    def plants(x):
        p.poly([(x - 28, 510), (x + 28, 510), (x + 20, 440), (x - 20, 440)], fill=(120, 80, 60), ol=INK, w=2)
        for _ in range(9):
            lx, ly = x + rng.uniform(-40, 40), 440 - rng.uniform(30, 150)
            p.ell(lx, ly, 14, 36, fill=(40 + rng.randint(0, 40), 110 + rng.randint(0, 60), 60), ol=INK, w=1.5)

    def panels(x0):
        for i in range(3):
            for j in range(4):
                xx, yy = x0 + i * 62, 60 + j * 100
                p.poly([(xx, yy), (xx + 54, yy), (xx + 54, yy + 90), (xx, yy + 90)], fill=shade(wallc, 0.75 + 0.15 * ((i + j) % 2)), ol=shade(wallc, 0.5), w=1.5, smooth=1)

    def lamps(x):
        p.line([(x, 0), (x, 90)], INK, 2)
        p.poly([(x - 28, 125), (x + 28, 125), (x + 14, 90), (x - 14, 90)], fill=acc, ol=INK, w=2)
        pg.ell(x, 135, 46, 30, fill=acc + (170,))

    def curtain(x0, x1):
        i = 0
        for x in range(int(x0), int(x1), 22):
            p.poly([(x, 0), (x + 22, 0), (x + 22, 510), (x, 510)], fill=shade(wallc, 1.1 if i % 2 else 0.8))
            i += 1

    {"window": window, "neon": neon, "posters": posters}[e["center"]]()
    for i, s in enumerate(e["sides"][:2]):
        left = i % 2 == 0
        if s == "shelves":
            shelves(20, 215) if left else shelves(1065, 1260)
        elif s == "plants":
            plants(80 if left else 1200)
        elif s == "panels":
            panels(15 if left else 1075)
        elif s == "lamps":
            lamps(130 if left else 1150)
        else:
            curtain(0, 150) if left else curtain(1130, 1280)
    for cx in (GX, HX):
        pg.ell(cx, 270, 210, 240, fill=(255, 245, 230, 34))
    glow = glow.filter(ImageFilter.GaussianBlur(14 * u))
    big = Image.alpha_composite(big.convert("RGBA"), glow).convert("RGB")
    bg = big.resize((SW, SH), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1.0 * u))
    # foreground: desk, props, mics, vignette
    fgb = Image.new("RGBA", (int(1280 * 2 * u), int(720 * 2 * u)), (0, 0, 0, 0))
    q = P(fgb, 2 * u)
    dk = hexrgb(e["desk"])
    q.poly([(0, 508), (1280, 508), (1280, 532), (0, 532)], fill=shade(dk, 1.35))
    q.poly([(0, 532), (1280, 532), (1280, 720), (0, 720)], fill=dk)
    q.line([(0, 508), (1280, 508)], INK, 2.5)
    q.line([(0, 532), (1280, 532)], shade(dk, 0.6), 3)
    for _ in range(26):
        y, x = rng.uniform(540, 715), rng.uniform(0, 1100)
        q.line([(x, y), (x + rng.uniform(60, 180), y + rng.uniform(-2, 2))], shade(dk, 0.85), 1.2)
    for x in (150, 1130):
        q.poly([(x - 14, 508), (x + 14, 508), (x + 12, 470), (x - 12, 470)], fill=(235, 235, 235), ol=INK, w=2)
        q.ell(x + 16, 490, 8, 10, ol=INK, w=2.5)
    for cx, dr in ((GX, -1), (HX, 1)):
        mx, my = cx + dr * 80, 340
        q.limb([(cx + dr * 215, 510), (cx + dr * 190, 430), (mx + dr * 8, my + 34)], 6, (50, 50, 56), INK, 1.5)
        q.limb([(mx - dr * 9, my - 26), (mx + dr * 9, my + 24)], 24, (38, 38, 44), INK, 2)
        q.line([(mx - dr * 6, my - 10), (mx + dr * 6, my - 4)], (120, 120, 130), 3)
    fgb = fgb.resize((SW, SH), Image.LANCZOS)
    yy, xx = np.mgrid[0:SH, 0:SW].astype(np.float32)
    r = np.sqrt(((xx - SW / 2) / (SW / 2)) ** 2 + ((yy - SH / 2) / (SH / 2)) ** 2)
    a = (np.clip((r - 0.75) / 0.9, 0, 1) ** 1.5 * 140).astype(np.uint8)
    vg = np.zeros((SH, SW, 4), np.uint8)
    vg[..., 3] = a
    fg = Image.alpha_composite(fgb, Image.fromarray(vg))
    return bg, fg

def make_chars(e, gface, u):
    ho = dict(kind=e["host_kind"], color=e["host_color"], accent=e["host_accent"])
    hl = dict(hat=e["host_hat"], hat_color=e["host_hat_color"], hair="short", hair_color="#1c1816", beard="none", glasses=False)
    go = dict(kind=e["guest_kind"], color=e["guest_color"], accent=e["guest_accent"])
    gl = dict(hat=e["guest_hat"], hat_color=e["guest_hat_color"], hair=e["guest_hair"], hair_color=e["guest_hair_color"],
              beard=e["guest_beard"], glasses=e["guest_glasses"])
    return {"G": Char(gface, go, gl, u), "H": Char(HOST_FACE, ho, hl, u)}

def compose(chars, bg, fg, sts, u):
    sc = bg.copy()
    for k, cx in (("G", GX), ("H", HX)):
        sp = chars[k].render(sts[k])
        sc.paste(sp, (int((cx - 230) * u), int(70 * u)), sp)
    sc.paste(fg, (0, 0), fg)
    return sc

# ================= audio =================
def voice_path(name):
    p = f"voices/{name}.onnx"
    if os.path.exists(p):
        return p
    try:
        loc, spk, q = name.split("-", 2)
        base = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{loc[:2]}/{loc}/{spk}/{q}/{name}"
        for ext in (".onnx", ".onnx.json"):
            r = requests.get(base + ext, timeout=900)
            r.raise_for_status()
            open(f"voices/{name}{ext}", "wb").write(r.content)
        return p
    except Exception:
        return voice_path("en_US-lessac-medium") if name != "en_US-lessac-medium" else voice_path(HOST_VOICE)

def tts(text, voice, scale):
    key = hashlib.md5(f"{voice}|{scale:.2f}|{text}".encode()).hexdigest()[:20]
    out = f"work/{key}.wav"
    if not os.path.exists(out):
        subprocess.run([sys.executable, "-m", "piper", "-m", voice_path(voice), "-f", out, "--length-scale", f"{scale:.2f}",
                        "--noise-scale", "0.8", "--noise-w", "0.9"], input=text.encode(), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out

def rd(path):
    with wave.open(path) as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    if sr != SR:
        a = np.interp(np.linspace(0, len(a) - 1, int(len(a) * SR / sr)), np.arange(len(a)), a)
    rms = float(np.sqrt(np.mean(a ** 2) + 1e-9))
    a = a * min(4.0, 0.1 / rms)
    return np.tanh(a).astype(np.float32)

def wr(path, a):
    a = np.clip(a, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())

def build_audio(lines, g, pace):
    chunks, tl, t = [], [], 0.0
    for l in lines:
        jit = 0.97 + (int(hashlib.md5(l["t"].encode()).hexdigest()[:2], 16) / 255) * 0.07
        v, sc = (HOST_VOICE, pace * jit) if l["s"] == "H" else (g["voice"], pace * g["pace_mul"] * jit)
        a = rd(tts(l["t"], v, sc))
        gap = 0.28 if l["s"] == "H" else 0.45
        tl.append({"s": l["s"], "a": t, "b": t + len(a) / SR, "t": l["t"], "k": l.get("k", ""), "sec": l.get("sec", 0)})
        chunks += [a, np.zeros(int(SR * gap), np.float32)]
        t += len(a) / SR + gap
    return np.concatenate(chunks), tl

def music(mood, n):
    L = 32.0
    m = int(SR * L)
    t = np.arange(m) / SR
    notes = {"calm": [110, 164.8, 220], "tense": [98, 116.5, 146.8], "hopeful": [130.8, 164.8, 196],
             "dark": [82.4, 98, 123.5], "curious": [110, 138.6, 185]}[mood]
    sig = np.zeros(m, np.float32)
    for f in notes:
        f = round(f * L) / L
        sig += np.sin(2 * np.pi * f * t + random.random() * 6.28).astype(np.float32)
    sig = sig / len(notes) * (0.65 + 0.35 * np.sin(2 * np.pi * t / 16)).astype(np.float32)
    out = np.resize(sig, n).astype(np.float32)
    k = min(n // 2, int(2 * SR))
    ramp = np.linspace(0, 1, k, dtype=np.float32)
    out[:k] *= ramp
    out[-k:] *= ramp[::-1]
    return out * 0.045

def feats(v, n, hop):
    a = np.zeros(n * hop, np.float32)
    m = min(len(v), n * hop)
    a[:m] = v[:m]
    env, zc = np.zeros(n, np.float32), np.zeros(n, np.float32)
    for s in range(0, n, 4000):
        e = min(n, s + 4000)
        blk = a[s * hop:e * hop].reshape(e - s, hop)
        env[s:e] = np.sqrt((blk ** 2).mean(1) + 1e-10)
        sg = np.signbit(blk)
        zc[s:e] = (sg[:, 1:] != sg[:, :-1]).mean(1)
    ref = np.percentile(env[env > 0.003], 95) if (env > 0.003).any() else 1.0
    return np.clip(env / ref, 0, 1.3), zc

def viseme(e, z):
    if e < 0.10:
        return 0
    if e < 0.25:
        return 1
    if z > 0.18:
        return 5
    if e > 0.75:
        return 3
    if z < 0.05 and e < 0.6:
        return 4
    return 2

# ================= camera / text =================
def plan_cams(tl, short, cut_rate):
    rate = {"fast": (2.6, 4.8), "medium": (4.0, 7.5), "slow": (6.0, 11.0)}[cut_rate]
    shots = []
    def add(t0, t1, foc, z, dx=0, dy=0):
        shots.append([t0, t1, foc, z, z * random.uniform(1.03, 1.08), dx, dy])
    for ln in tl:
        s, a, b = ln["s"], ln["a"], ln["b"]
        other = "H" if s == "G" else "G"
        t, first = a, True
        while t < b - 0.05:
            seg = min(b, t + random.uniform(*rate))
            if b - seg < 1.4:
                seg = b
            if first:
                kind = random.choices(["close", "mid", "wide"], [0.6, 0.3, 0.1])[0] if not short else random.choices(["close", "mid"], [0.7, 0.3])[0]
            else:
                kind = random.choices(["close", "mid", "react", "wide"], [0.35, 0.3, 0.25, 0.1])[0] if not short else random.choices(["close", "mid", "react"], [0.5, 0.3, 0.2])[0]
            if short:
                foc = other if kind == "react" else s
                z = {"close": random.uniform(1.35, 1.55), "mid": 1.0, "react": random.uniform(1.2, 1.4)}[kind]
                add(t, seg, foc, z, random.uniform(-20, 20), random.uniform(0, 40))
            elif kind in ("wide", "mid"):
                add(t, seg, "both", 1.0 if kind == "wide" else random.uniform(1.25, 1.4), 0, 20)
            else:
                foc = other if kind == "react" else s
                add(t, seg, foc, random.uniform(1.85, 2.3), random.uniform(-25, 25), random.uniform(10, 50))
            t, first = seg, False
    return shots

def cam_rect(shot, t, SW, SH, OW, OH, u):
    t0, t1, foc, z0, z1, dx, dy = shot
    k = min(1.0, max(0.0, (t - t0) / max(0.1, t1 - t0)))
    z = z0 + (z1 - z0) * k
    asp = OW / OH
    vh = SH / z
    vw = vh * asp
    if vw > SW:
        vw = SW
        vh = vw / asp
    cxv = {"G": GX, "H": HX, "both": (GX + HX) / 2}[foc]
    cyv = (300 + dy) if foc != "both" else (320 + dy / 2)
    cx, cy = (cxv + dx) * u, cyv * u
    x0 = min(max(cx - vw / 2, 0), SW - vw)
    y0 = min(max(cy - vh / 2, 0), SH - vh)
    return (x0, y0, x0 + vw, y0 + vh)

def caption_chunks(tl, f, maxw, per):
    chunks = []
    sp = f.getlength(" ")
    for ln in tl:
        ws = ln["t"].split()
        if not ws:
            continue
        tot, t, dur = sum(len(w) + 1 for w in ws), ln["a"], ln["b"] - ln["a"]
        timed = []
        for w in ws:
            d = dur * (len(w) + 1) / tot
            timed.append((w, t, t + d))
            t += d
        i = 0
        while i < len(timed):
            grp = [timed[i]]
            i += 1
            while i < len(timed) and len(grp) < per and not grp[-1][0].endswith((".", "?", "!", ",", ";", ":")):
                grp.append(timed[i])
                i += 1
            lines, cur, w = [], [], 0.0
            for wd, a, b in grp:
                wl = f.getlength(wd)
                if cur and w + sp + wl > maxw:
                    lines.append((cur, w))
                    cur, w = [], 0.0
                x = w + (sp if cur else 0)
                cur.append((wd, x, a, b))
                w = x + wl
            lines.append((cur, w))
            chunks.append({"a": grp[0][1], "b": grp[-1][2], "lines": lines})
    return chunks

def draw_callout(d, OW, OH, text, tt, dur, accent, y):
    e = ease_back(min(1.0, tt / 0.28))
    fade = min(1.0, max(0.0, (dur - tt) / 0.25))
    size = int(OW * 0.06 * (0.45 + 0.55 * min(e, 1.15)) * (0.6 + 0.4 * fade))
    f = font(size)
    text = text.upper()
    w = f.getlength(text)
    x, pad = (OW - w) / 2, size * 0.45
    d.rounded_rectangle([x - pad, y - pad * 0.5, x + w + pad, y + size * 1.25], radius=int(size * 0.35), fill=accent)
    d.text((x, y), text, font=f, fill=(15, 15, 18))

def draw_lower(d, OW, OH, title, tt, accent):
    k = min(ease_out(min(1.0, tt / 0.45)), ease_out(min(1.0, max(0.0, (3.4 - tt) / 0.4))))
    size = int(OW * 0.028)
    f = font(size)
    w = f.getlength(title) + size * 1.8
    x, y = -w + (w + OW * 0.04) * k, OH * 0.06
    d.rectangle([x, y, x + w, y + size * 2.2], fill=(14, 14, 18))
    d.rectangle([x, y, x + 8, y + size * 2.2], fill=accent)
    d.text((x + size * 1.0, y + size * 0.55), title, font=f, fill=(255, 255, 255))

# ================= video =================
def render_video(short, tl, voice, chars, bg, fg, e, u, titles, out):
    FPS = 25 if short else 15
    OW, OH = (720, 1280) if short else (1280, 720)
    SW, SH = bg.size
    n = int((tl[-1]["b"] + 1.2) * FPS)
    hop = SR // FPS
    env, zc = feats(voice, n, hop)
    es = np.convolve(env, np.ones(3) / 3, mode="same")
    spk = [None] * n
    for l in tl:
        for f in range(int(l["a"] * FPS), min(n, int((l["b"] + 0.08) * FPS))):
            spk[f] = l["s"]
    w = max(2, int(0.25 * FPS))
    mx = np.lib.stride_tricks.sliding_window_view(np.pad(es, (w, w), mode="edge"), 2 * w + 1).max(1)
    emph, last = [False] * n, -99
    for f in range(n):
        if spk[f] and es[f] >= mx[f] - 1e-6 and es[f] > 0.62 and f - last > 0.45 * FPS:
            emph[f], last = True, f
    vis = [viseme(es[f], zc[f]) if spk[f] else 0 for f in range(n)]
    shots = plan_cams(tl, short, e["cut_rate"])
    csz = int(e["caption_size"] * (1.3 if short else 1.0))
    cf = font(csz)
    chunks = caption_chunks(tl, cf, OW * 0.86, 3 if short else 5)
    lh, sw = int(csz * 1.28), max(2, csz // 12)
    acc, capc = hexrgb(e["accent"]), hexrgb(e["caption_color"])
    callouts = [(l["a"] + 0.4, l["a"] + 3.0, l["k"]) for l in tl if l.get("k")]
    lowers = []
    if not short and titles:
        seen = set()
        for l in tl:
            if l["sec"] not in seen and l["sec"] < len(titles):
                seen.add(l["sec"])
                lowers.append((l["a"], l["a"] + 3.4, titles[l["sec"]]))
    ctl = {"G": Ctl("G", chars["G"].face, random.Random(random.randint(1, 10 ** 6)), e["gesture"]),
           "H": Ctl("H", HOST_FACE, random.Random(random.randint(1, 10 ** 6)), e["gesture"])}
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(FPS), "-i", "-",
           "-i", "work/mix.wav", "-c:v", "libx264", "-preset", "veryfast", "-tune", "animation", "-crf", "24", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-shortest", out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    si = ci = cli = lti = 0
    for f in range(n):
        t = f / FPS
        sp = spk[f]
        sts = {k: ctl[k].step(t, FPS, sp, emph[f] and sp is not None, vis[f]) for k in "GH"}
        scene = compose(chars, bg, fg, sts, u)
        while si + 1 < len(shots) and shots[si + 1][0] <= t:
            si += 1
        fr = scene.resize((OW, OH), Image.BILINEAR, box=cam_rect(shots[si], t, SW, SH, OW, OH, u))
        d = ImageDraw.Draw(fr)
        while ci + 1 < len(chunks) and chunks[ci + 1]["a"] <= t:
            ci += 1
        if chunks and chunks[ci]["a"] <= t < chunks[ci]["b"] + 0.3:
            ch = chunks[ci]
            yoff = (1 - ease_out(min(1.0, (t - ch["a"]) / 0.12))) * 16
            if short:
                cy0 = OH * 0.62
            elif e["caption_pos"] == "mid":
                cy0 = OH * 0.70
            else:
                cy0 = OH * 0.82
            cy0 -= (len(ch["lines"]) - 1) * lh
            for li, (wsx, wd_) in enumerate(ch["lines"]):
                x0 = (OW - wd_) / 2
                for wd, x, a, b in wsx:
                    d.text((x0 + x, cy0 + li * lh + yoff), wd, font=cf, fill=acc if a <= t < b else capc,
                           stroke_width=sw, stroke_fill=(0, 0, 0))
        while cli < len(callouts) and callouts[cli][1] < t:
            cli += 1
        if cli < len(callouts) and callouts[cli][0] <= t < callouts[cli][1]:
            c = callouts[cli]
            draw_callout(d, OW, OH, c[2], t - c[0], c[1] - c[0], acc, OH * (0.13 if short else 0.10))
        while lti < len(lowers) and lowers[lti][1] < t:
            lti += 1
        if lti < len(lowers) and lowers[lti][0] <= t < lowers[lti][1]:
            draw_lower(d, OW, OH, lowers[lti][2], t - lowers[lti][0], acc)
        try:
            ff.stdin.write(fr.tobytes())
        except BrokenPipeError:
            break
        if f % 3000 == 0:
            print(f"frame {f}/{n}  elapsed {(time.time() - T0) / 60:.0f} min", flush=True)
    try:
        ff.stdin.close()
    except Exception:
        pass
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg failed")

def thumbnail(chars, bg, fg, u, text, e, path):
    stG = base_state(chars["G"].face)
    stG.update(mouth=3, brow=6.0, lid=chars["G"].face["droop"] * 0.5, tilt=-2.0)
    stH = base_state(HOST_FACE)
    stH.update(R=(264, 252, "relax"), brow=1.0)
    sc = compose(chars, bg, fg, {"G": stG, "H": stH}, u)
    W, H = 1280, 720
    cv = ImageEnhance.Brightness(sc.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(6))).enhance(0.45)
    def crop(cx):
        chh = 400 * u
        cw = chh * 520 / 720
        x0, y0 = cx * u - cw / 2, 300 * u - chh / 2
        return sc.resize((520, 720), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + chh))
    def mask(left_fade):
        a = np.ones((720, 520), np.float32)
        ramp = np.linspace(0, 1, 100)
        if left_fade:
            a[:, :100] = ramp[None, :]
        else:
            a[:, -100:] = ramp[::-1][None, :]
        return Image.fromarray((a * 255).astype(np.uint8))
    cv.paste(crop(GX), (0, 0), mask(False))
    cv.paste(crop(HX), (760, 0), mask(True))
    cv = ImageEnhance.Contrast(ImageEnhance.Color(cv).enhance(1.2)).enhance(1.1)
    parts = [p.strip().upper() for p in text.split("|") if p.strip()][:2] or ["WATCH THIS"]
    d = ImageDraw.Draw(cv)
    sizes = []
    for p_ in parts:
        s = 170
        while font(s).getlength(p_) > 720 and s > 60:
            s -= 6
        sizes.append(s)
    total = sum(sizes) + 20 * (len(parts) - 1)
    y = (H - total) / 2 - 20
    for i, (p_, s) in enumerate(zip(parts, sizes)):
        f = font(s)
        d.text(((W - f.getlength(p_)) / 2, y), p_, font=f, fill=(255, 255, 255) if i == 0 else hexrgb(e["accent"]),
               stroke_width=9, stroke_fill=(0, 0, 0))
        y += s + 20
    cv.save(path, quality=92)

# ================= upload =================
def publish_at():
    if not PUB_HOUR:
        return None
    bd = dt.timezone(dt.timedelta(hours=6))
    now = dt.datetime.now(bd)
    t = now.replace(hour=int(PUB_HOUR), minute=0, second=0, microsecond=0)
    if t < now + dt.timedelta(minutes=20):
        t += dt.timedelta(days=1)
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

def upload(path, meta, thumb):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    cr = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"].strip(), token_uri="https://oauth2.googleapis.com/token",
                     client_id=os.environ["YT_CLIENT_ID"].strip(), client_secret=os.environ["YT_CLIENT_SECRET"].strip())
    cr.refresh(Request())
    yt = build("youtube", "v3", credentials=cr)
    pa = publish_at()
    def go(synthetic):
        status = {"privacyStatus": "private" if pa else "public", "selfDeclaredMadeForKids": False}
        if synthetic:
            status["containsSyntheticMedia"] = True
        if pa:
            status["publishAt"] = pa
        body = {"snippet": {"title": meta["title"], "description": meta["description"], "tags": meta["tags"], "categoryId": "27",
                            "defaultLanguage": "en", "defaultAudioLanguage": "en"}, "status": status}
        req = yt.videos().insert(part="snippet,status", body=body,
                                 media_body=MediaFileUpload(path, chunksize=32 * 1024 * 1024, resumable=True))
        resp, tries = None, 0
        while resp is None:
            try:
                _, resp = req.next_chunk()
            except HttpError as ex:
                if ex.resp.status in (500, 502, 503, 504) and tries < 8:
                    tries += 1
                    time.sleep(5 * tries)
                else:
                    raise
        return resp
    try:
        resp = go(True)
    except HttpError as ex:
        if ex.resp.status == 400:
            resp = go(False)
        else:
            raise
    print("uploaded", resp["id"], "publishAt", pa, flush=True)
    if thumb:
        try:
            yt.thumbnails().set(videoId=resp["id"], media_body=MediaFileUpload(thumb)).execute()
        except Exception as ex:
            print("thumbnail failed:", ex)

# ================= Friday post =================
def friday_post(state):
    topic, angle = pick_topic(state)
    j = llm_json(f"Topic: {topic}\nAngle: {angle}\nWrite a Friday community post for a channel about self-improvement and psychology. JSON keys: "
                 "text (90-120 words, thoughtful, ends with a question to the audience, no links, no sources), "
                 "quote (a short original insight, max 14 words), hashtags (list of 4).")
    e, u = rand_edit(), 1.0
    chars = make_chars(e, rand_face(random.randint(1, 10 ** 6)), u)
    bg, fg = build_studio(e, u)
    st = base_state(HOST_FACE)
    st.update(R=(264, 252, "relax"), mouth=0)
    sts = {"G": base_state(chars["G"].face), "H": st}
    sc = compose(chars, bg, fg, sts, u)
    chh = 420 * u
    img = sc.resize((1080, 1080), Image.LANCZOS, box=(HX * u - chh / 2, 290 * u - chh / 2, HX * u + chh / 2, 290 * u + chh / 2))
    grad = np.zeros((1080, 1080, 4), np.uint8)
    grad[..., 3] = (np.clip((np.arange(1080) - 520) / 400, 0, 1) * 215).astype(np.uint8)[:, None]
    img = Image.alpha_composite(img.convert("RGBA"), Image.fromarray(grad)).convert("RGB")
    d = ImageDraw.Draw(img)
    f = font(58)
    words, lines_, cur = str(j.get("quote", topic)).split(), [], ""
    for wd in words:
        if f.getlength((cur + " " + wd).strip()) <= 900:
            cur = (cur + " " + wd).strip()
        else:
            lines_.append(cur)
            cur = wd
    lines_.append(cur)
    y = 1040 - len(lines_) * 74
    for ln in lines_:
        d.text(((1080 - f.getlength(ln)) / 2, y), ln, font=f, fill=(255, 255, 255), stroke_width=5, stroke_fill=(0, 0, 0))
        y += 74
    day = dt.date.today().isoformat()
    img.save(f"posts/{day}.png")
    txt = str(j.get("text", "")) + "\n\n" + " ".join("#" + str(h).lstrip("#") for h in j.get("hashtags", []))
    open(f"posts/{day}.txt", "w").write(re.sub(r"https?://\S+", "", txt))
    state["topics"].append(topic)
    save_state(state)

# ================= main =================
def main():
    state = load_state()
    if KIND == "post":
        return friday_post(state)
    short = KIND == "short"
    topic, angle = pick_topic(state)
    g = make_guest(topic, state)
    print("topic:", topic, "| guest:", g["name"], flush=True)
    if short:
        lines, titles = script_short(topic, angle, g), []
    else:
        lines, titles = script_long(topic, angle, g)
    if len(lines) < 6:
        raise RuntimeError("script too short")
    e = make_edit(topic, g, lines)
    pace = e["pace"]
    voice, tl = build_audio(lines, g, pace)
    if short and tl[-1]["b"] > 58:
        voice, tl = build_audio(lines, g, max(0.8, pace * 58 / tl[-1]["b"]))
    if not short and tl[-1]["b"] > LONG_MAX:
        mx = max(l["sec"] for l in lines)
        while tl[-1]["b"] > LONG_MAX and mx > 1:
            mx -= 1
            keep = [l for l in lines if l["sec"] < mx or l["sec"] == max(x["sec"] for x in lines)]
            lines = keep
            voice, tl = build_audio(lines, g, pace)
            if all(l["sec"] != mx for l in lines):
                continue
    mix = np.concatenate([voice, np.zeros(SR, np.float32)])
    mix += music(e["mood"], len(mix))
    wr("work/mix.wav", mix * 0.95)
    del mix
    u = 1.5 if short else 1.25
    chars = make_chars(e, rand_face(random.randint(1, 10 ** 6)), u)
    bg, fg = build_studio(e, u)
    chapters = []
    if not short:
        seen = set()
        for l in tl:
            if l["sec"] not in seen and l["sec"] < len(titles):
                seen.add(l["sec"])
                chapters.append((l["a"], titles[l["sec"]]))
        chapters = chapters[:40]
        if chapters:
            chapters[0] = (0, chapters[0][1])
    meta = make_meta(topic, lines, short, chapters)
    video = "out/video.mp4"
    render_video(short, tl, voice, chars, bg, fg, e, u, titles, video)
    thumb = None
    if not short:
        thumb = "out/thumb.jpg"
        thumbnail(chars, bg, fg, u, meta["thumb"], e, thumb)
    json.dump({"topic": topic, "guest": g, "edit": e, "meta": meta,
               "lines": [{"s": l["s"], "t": l["t"]} for l in tl], "minutes": round(tl[-1]["b"] / 60, 1)},
              open("out/info.json", "w"), indent=1)
    if os.getenv("YT_REFRESH_TOKEN"):
        upload(video, meta, thumb)
    state["topics"].append(topic)
    state["guests"].append(g["name"])
    save_state(state)

if __name__ == "__main__":
    main()
