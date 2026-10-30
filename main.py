#!/usr/bin/env python3
import os, re, sys, json, random, subprocess, wave, datetime as dt
import numpy as np, requests
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance

KIND = (os.getenv("KIND") or "short").strip().lower()
PUB_HOUR = (os.getenv("PUBLISH_HOUR_BD") or "").strip()
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA = "http://127.0.0.1:11434"
FPS, SR = 24, 22050
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
for d in ("work", "assets", "posts", "out", "voices"):
    os.makedirs(d, exist_ok=True)

HOST_VOICE = "en_US-ryan-high"
MALE = ["en_GB-alan-medium", "en_US-joe-medium", "en_GB-northern_english_male-medium"]
FEMALE = ["en_US-amy-medium", "en_GB-jenny_dioco-medium", "en_US-lessac-medium", "en_GB-alba-medium"]
HOST_BASE = ("photorealistic portrait photo of Alex, a 32 year old man, short dark brown hair, light stubble, "
             "calm confident expression, wearing a white shirt, sitting at a podcast desk with a microphone, "
             "plain dark studio, upper body, looking at camera, soft cinematic lighting, 85mm, natural skin texture")
HOST_OUTFITS = ["crisp white shirt with a navy blazer", "white knit sweater", "white t-shirt under a charcoal overcoat",
                "white linen shirt with rolled sleeves", "white turtleneck with a beige jacket",
                "white shirt with a dark green cardigan"]
AREAS = ["cognitive biases", "persuasion and influence", "attachment and relationships", "motivation and habits",
         "fear and anxiety", "social psychology", "decision making", "memory and perception", "emotional intelligence",
         "personality", "body language", "stoic and philosophical psychology", "group behavior and history",
         "willpower and discipline", "confidence and self-image", "attraction and charisma", "grief and resilience",
         "creativity and flow", "moral psychology", "dark psychology and manipulation awareness"]
FORMAT = 'Return JSON: {"lines":[{"s":"H","t":"..."},{"s":"G","t":"..."}]}'
SYS = ("You write dialogue for a serious, professional psychology podcast. Host Alex (s=H) asks short, sharp questions "
       "(max 18 words). The guest (s=G) gives deep, concrete answers using real psychological concepts, well-known "
       "historical episodes, famous proverbs and thought experiments. Never invent studies, statistics or quotes "
       "attributed to real people; mention research only in general, well-established terms. No filler greetings, "
       "no sponsor talk, no links. Everything in English. Output valid JSON only.")

# ---------------- local LLM ----------------
def llm(prompt, system=SYS, js=False, temp=0.8):
    body = {"model": MODEL, "prompt": prompt, "system": system, "stream": False,
            "options": {"temperature": temp, "num_ctx": 8192}}
    if js:
        body["format"] = "json"
    r = requests.post(OLLAMA + "/api/generate", json=body, timeout=3600)
    return r.json()["response"].strip()

def llm_json(prompt, system=SYS, tries=5, temp=0.7):
    for _ in range(tries):
        try:
            return json.loads(llm(prompt, system, True, temp))
        except Exception:
            pass
    raise RuntimeError("LLM JSON failed")

def clean(x):
    out = []
    if not isinstance(x, list):
        return out
    for d in x:
        try:
            s = str(d["s"]).strip().upper()[:1]
            t = re.sub(r"\s+", " ", str(d["t"])).strip()
            if s and s in "HG" and len(t) > 3:
                out.append({"s": s, "t": t})
        except Exception:
            pass
    return out

def wc(lines):
    return sum(len(l["t"].split()) for l in lines)

def refine(lines, topic, passes):
    for _ in range(passes):
        crit = llm("Critique this psychology podcast dialogue. List: invented studies/quotes, shallow or generic parts, "
                   "repetition, host questions longer than 18 words, weak hooks. Max 120 words.\n" + json.dumps(lines),
                   "You are a strict editor.", False, 0.3)
        try:
            j = llm_json("Rewrite the dialogue fixing every issue. Keep similar length and the same format.\nISSUES: "
                         + crit + "\nDIALOGUE: " + json.dumps(lines) + "\n" + FORMAT)
            new = clean(j.get("lines"))
            if new and 0.8 * wc(lines) <= wc(new) <= 1.25 * wc(lines):
                lines = new
        except Exception:
            pass
    return lines

# ---------------- state / topics ----------------
def load_state():
    try:
        return json.load(open("state.json"))
    except Exception:
        return {"topics": [], "guests": []}

def save_state(s):
    json.dump(s, open("state.json", "w"), indent=1)

def sim(a, b):
    sa, sb = set(a.lower().split()), set(b.lower().split())
    return len(sa & sb) / max(1, len(sa | sb))

def pick_topic(state):
    recent = state["topics"][-100:]
    t, angle = "", ""
    for _ in range(6):
        area = random.choice(AREAS)
        j = llm_json(f"Psychology area: {area}\nAlready covered (never repeat or paraphrase): {json.dumps(recent)}\n"
                     'Propose ONE fresh, specific, intriguing topic for a deep expert conversation. '
                     'JSON: {"topic":"...","angle":"one sentence on the surprising angle"}', temp=1.0)
        t, angle = str(j.get("topic", "")).strip(), str(j.get("angle", ""))
        if t and not any(sim(t, r) > 0.5 for r in recent):
            break
    return t or "The psychology of first impressions", angle

def make_guest(topic, state):
    used = [g for g in state["guests"][-60:]]
    g = llm_json(f"Invent a FICTIONAL expert guest for a podcast about: {topic}. Not a real person, not resembling anyone famous. "
                 f"Avoid these names: {used}.\n"
                 'JSON keys: name, gender ("male" or "female"), age (30-75), role, look (face, hair, ethnicity, 15 words), '
                 'outfit (a fresh clothing style), studio (a distinct podcast studio interior, 15 words), style (5 words about speaking style).',
                 temp=1.0)
    g["name"] = str(g.get("name", "Dr. Sam Reed"))
    g["gender"] = "female" if str(g.get("gender", "")).lower().startswith("f") else "male"
    g["age"] = int(clamp(g.get("age"), 30, 75, 45))
    for k, d in (("role", "psychologist"), ("look", "kind eyes, short hair"), ("outfit", "grey blazer"),
                 ("studio", "warm wooden studio with bookshelves"), ("style", "calm, precise, thoughtful")):
        g[k] = str(g.get(k) or d)
    g["voice"] = random.choice(FEMALE if g["gender"] == "female" else MALE)
    return g

# ---------------- scripts ----------------
def script_short(topic, angle, g):
    j = llm_json(f"Topic: {topic}\nAngle: {angle}\nGuest: {g['name']}, {g['role']}, style: {g['style']}\n"
                 "Write a dialogue of 105-120 words total. Start with a hook question from Alex. 4-5 exchanges. "
                 "End with a memorable closing line from the guest.\n" + FORMAT)
    return refine(clean(j.get("lines")), topic, 3)

def script_long(topic, angle, g):
    o = llm_json(f"Topic: {topic}\nAngle: {angle}\nPlan a 7-minute deep-dive conversation in 6 sections that build on each other "
                 "(a historical case, the core mechanism, a proverb or philosophical lens, a counter-intuitive twist, "
                 'practical application, closing insight). JSON: {"sections":[{"title":"...","key_idea":"..."}]}')
    secs = o.get("sections", [])[:6]
    lines = []
    for i, s in enumerate(secs):
        extra = ("Open with a gripping hook question." if i == 0 else
                 "Close with a memorable final line from the guest." if i == len(secs) - 1 else
                 "Continue naturally, no re-introductions.")
        j = llm_json(f"Topic: {topic}\nGuest: {g['name']} ({g['role']}, style: {g['style']})\n"
                     f"Section {i+1}/{len(secs)}: {s.get('title')} - {s.get('key_idea')}\n"
                     f"Previously: {json.dumps(lines[-4:])}\n{extra}\nWrite 170-210 words, 5-7 exchanges.\n" + FORMAT)
        sec = clean(j.get("lines"))
        if sec:
            lines += refine(sec, topic, 2)
    return lines

def clamp(v, a, b, d):
    try:
        return min(b, max(a, float(v)))
    except Exception:
        return d

def hexok(c, d):
    return c if isinstance(c, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", c) else d

def make_edit(topic, g, lines):
    ex = " ".join(l["t"] for l in lines)[:900]
    j = llm_json(f"You are a video editing director. Topic: {topic}. Excerpt: {ex}\n"
                 "Choose an editing style that fits the mood and feels different from a generic template. JSON keys: "
                 'mood ("calm"|"tense"|"hopeful"|"dark"|"curious"), zoom (0.03-0.10 speaking zoom), caption_color (hex like #FFD400), '
                 'accent (hex), caption_pos ("bottom"|"mid"), caption_size (36-54), dim (0.5-0.85 brightness of non-speaker), '
                 'guest_side ("left"|"right"), pace (0.92-1.05 speech length scale).', temp=1.0)
    mood = j.get("mood") if j.get("mood") in ("calm", "tense", "hopeful", "dark", "curious") else "calm"
    return {"mood": mood, "zoom": clamp(j.get("zoom"), 0.03, 0.10, 0.06),
            "caption_color": hexok(j.get("caption_color"), "#FFFFFF"), "accent": hexok(j.get("accent"), "#FFC21A"),
            "caption_pos": "mid" if j.get("caption_pos") == "mid" else "bottom",
            "caption_size": int(clamp(j.get("caption_size"), 36, 54, 44)), "dim": clamp(j.get("dim"), 0.5, 0.85, 0.7),
            "guest_side": "right" if j.get("guest_side") == "right" else "left",
            "pace": clamp(j.get("pace"), 0.92, 1.05, 1.0)}

def make_meta(topic, lines, short):
    ex = " ".join(l["t"] for l in lines)[:1500]
    j = llm_json(f"Topic: {topic}\nTranscript excerpt: {ex}\nCreate YouTube SEO metadata for the channel's English psychology podcast. "
                 "JSON keys: title (max 62 chars, curiosity-driven but honest, no channel name), "
                 "description (150-230 words, keywords in first two lines, summary, then 5 hashtags; NO links, NO sources, NO real people's names), "
                 "tags (12 strings), thumb_text (two lines separated by '|', max 3 words each).")
    title = re.sub(r'["\']', "", str(j.get("title") or topic)).strip()[:62]
    desc = re.sub(r"https?://\S+|www\.\S+", "", str(j.get("description", ""))).strip()
    desc += "\n\nThis is an AI-generated fictional conversation created for educational purposes."
    tags = [str(t)[:30] for t in (j.get("tags") or [])][:12] or ["psychology"]
    if short:
        title += " #Shorts"
        desc += "\n#Shorts"
    return {"title": title, "description": desc, "tags": tags, "thumb": str(j.get("thumb_text", "WATCH THIS|NOW"))}

# ---------------- images (local Stable Diffusion Turbo) ----------------
_pipe = None
def sd():
    global _pipe
    if _pipe is None:
        import torch
        from diffusers import AutoPipelineForText2Image
        _pipe = AutoPipelineForText2Image.from_pretrained("stabilityai/sd-turbo", torch_dtype=torch.float32)
        _pipe.set_progress_bar_config(disable=True)
    return _pipe

def txt2img(prompt, seed, size=512):
    import torch
    return sd()(prompt=prompt, num_inference_steps=3, guidance_scale=0.0, height=size, width=size,
                generator=torch.Generator().manual_seed(seed)).images[0]

def img2img(prompt, init, seed, strength=0.55):
    import torch
    from diffusers import AutoPipelineForImage2Image
    p = AutoPipelineForImage2Image.from_pipe(sd())
    return p(prompt=prompt, image=init, strength=strength, num_inference_steps=4, guidance_scale=0.0,
             generator=torch.Generator().manual_seed(seed)).images[0]

def host_image(studio):
    path = "assets/host_base.png"
    if not os.path.exists(path):
        txt2img(HOST_BASE, 20240611).save(path)   # Alex's fixed face
    base = Image.open(path).convert("RGB")
    outfit = random.choice(HOST_OUTFITS)
    prompt = (f"photorealistic portrait photo of Alex, a 32 year old man, short dark brown hair, light stubble, wearing {outfit}, "
              f"sitting at a podcast desk with a microphone in {studio}, upper body, looking at camera, soft cinematic lighting, 85mm")
    return img2img(prompt, base, random.randint(1, 10**6))

def guest_image(g):
    prompt = (f"photorealistic portrait photo of {g['name']}, a {g['age']} year old {g['gender']}, {g['look']}, wearing {g['outfit']}, "
              f"{g['role']}, sitting at a podcast desk with a microphone in {g['studio']}, upper body, looking at camera, "
              "soft cinematic lighting, 85mm, natural skin texture")
    return txt2img(prompt, random.randint(1, 10**6))

# ---------------- audio (local Piper TTS) ----------------
def voice_path(name):
    p = f"voices/{name}.onnx"
    if not os.path.exists(p):
        loc, spk, q = name.split("-", 2)
        base = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{loc[:2]}/{loc}/{spk}/{q}/{name}"
        for ext in (".onnx", ".onnx.json"):
            r = requests.get(base + ext, timeout=600)
            r.raise_for_status()
            open(f"voices/{name}{ext}", "wb").write(r.content)
    return p

def tts(text, voice, out, scale):
    subprocess.run([sys.executable, "-m", "piper", "-m", voice_path(voice), "-f", out, "--length-scale", f"{scale:.2f}",
                    "--noise-scale", "0.8", "--noise-w", "0.9"], input=text.encode(), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def rd(path):
    with wave.open(path) as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    if sr != SR:
        a = np.interp(np.linspace(0, len(a) - 1, int(len(a) * SR / sr)), np.arange(len(a)), a)
    return a.astype(np.float32)

def wr(path, a):
    a = np.clip(a, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())

def build_audio(lines, g, pace):
    chunks, tl, t = [], [], 0.0
    gs = pace * random.uniform(0.96, 1.08)
    for i, l in enumerate(lines):
        v, sc = (HOST_VOICE, pace) if l["s"] == "H" else (g["voice"], gs)
        p = f"work/l{i}.wav"
        tts(l["t"], v, p, sc)
        a = rd(p)
        gap = 0.25 if l["s"] == "H" else 0.4
        tl.append((l["s"], t, t + len(a) / SR, l["t"]))
        chunks += [a, np.zeros(int(SR * gap), np.float32)]
        t += len(a) / SR + gap
    return np.concatenate(chunks), tl

def music(mood, n):
    t = np.arange(n) / SR
    base = {"calm": [110, 164.8, 220], "tense": [98, 116.5, 146.8], "hopeful": [130.8, 164.8, 196],
            "dark": [82.4, 98, 123.5], "curious": [110, 138.6, 185]}[mood]
    m = sum(np.sin(2 * np.pi * f * t + random.random() * 6) for f in base) / len(base)
    m *= 0.6 + 0.4 * np.sin(2 * np.pi * t / random.uniform(14, 24))
    fade = np.minimum(1, np.minimum(t, t[-1] - t) / 2.0)
    return (m * fade * 0.05).astype(np.float32)

# ---------------- video rendering ----------------
def textbox(text, size, color, maxw):
    font = ImageFont.truetype(FONT, size)
    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines, cur = [], ""
    for w in text.split():
        test = (cur + " " + w).strip()
        if tmp.textlength(test, font=font) <= maxw:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    lh, pad = int(size * 1.3), int(size * 0.5)
    img = Image.new("RGBA", (maxw + 2 * pad, lh * len(lines) + pad), (0, 0, 0, 150))
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        w = d.textlength(l, font=font)
        d.text(((img.width - w) / 2, pad // 2 + i * lh), l, font=font, fill=color,
               stroke_width=max(2, size // 14), stroke_fill="black")
    return img

def build_caps(tl, W, short, edit):
    caps, size = [], int(edit["caption_size"] * (0.85 if short else 1))
    for s, a, b, text in tl:
        w = text.split()
        chunks = [" ".join(w[i:i + 8]) for i in range(0, len(w), 8)]
        tot, t = sum(len(c) for c in chunks), a
        for c in chunks:
            d = (b - a) * len(c) / tot
            caps.append((t, t + d, textbox(c, size, edit["caption_color"], int(W * 0.84))))
            t += d
    return caps

def render(short, himg, gimg, tl, voice, edit, title, out):
    W, H = (720, 1280) if short else (1280, 720)
    pw, ph = (W, H // 2) if short else (W // 2, H)
    if short:
        pos = {"G": (0, 0), "H": (0, ph)}
    else:
        gl = edit["guest_side"] == "left"
        pos = {"G": (0 if gl else pw, 0), "H": (pw if gl else 0, 0)}
    base = {k: ImageOps.fit(im.convert("RGB"), (int(pw * 1.15), int(ph * 1.15)), Image.LANCZOS)
            for k, im in (("G", gimg), ("H", himg))}
    caps = build_caps(tl, W, short, edit)
    tcard = textbox(title.replace(" #Shorts", ""), int(W * 0.05), edit["accent"], int(W * 0.82))
    n = int((tl[-1][2] + 1.0) * FPS)
    hop = SR // FPS
    env = np.array([np.sqrt(np.mean(voice[i * hop:(i + 1) * hop] ** 2) + 1e-9) if i * hop < len(voice) else 0
                    for i in range(n)])
    env = np.clip(env / (np.percentile(env, 95) + 1e-6), 0, 1)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-i", "work/mix.wav", "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", out],
                          stdin=subprocess.PIPE)
    ti, ci, last = 0, 0, "G"
    for f in range(n):
        t = f / FPS
        while ti < len(tl) - 1 and t >= tl[ti][2] + 0.15:
            ti += 1
        s = tl[ti]
        spk = s[0] if s[1] <= t < s[2] + 0.15 else None
        if spk:
            last = spk
        cv = Image.new("RGB", (W, H), (8, 8, 10))
        for k in "GH":
            z = 1 + 0.012 * (1 + np.sin(t / 5 + (k == "H"))) + (edit["zoom"] * env[f] if spk == k else 0)
            bw, bh = base[k].size
            cw, ch = bw / z, bh / z
            x0, y0 = (bw - cw) / 2, (bh - ch) / 2
            p = base[k].resize((pw, ph), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
            if k != last:
                p = ImageEnhance.Brightness(p).enhance(edit["dim"])
            cv.paste(p, pos[k])
        x, y = pos[last]
        ImageDraw.Draw(cv).rectangle([x, y + ph - 6, x + pw, y + ph], fill=edit["accent"])
        while ci < len(caps) and t >= caps[ci][1]:
            ci += 1
        if ci < len(caps) and caps[ci][0] <= t:
            c = caps[ci][2]
            if short:
                cy = H // 2 - c.height // 2
            elif edit["caption_pos"] == "mid":
                cy = int(H * 0.68 - c.height / 2)
            else:
                cy = H - c.height - int(H * 0.05)
            cv.paste(c, ((W - c.width) // 2, cy), c)
        if t < 3.5:
            cv.paste(tcard, ((W - tcard.width) // 2, int(H * 0.04)), tcard)
        ff.stdin.write(cv.tobytes())
    ff.stdin.close()
    ff.wait()

def thumbnail(himg, gimg, text, edit, path):
    W, H = 1280, 720
    c = Image.new("RGB", (W, H))
    gl = edit["guest_side"] == "left"
    c.paste(ImageOps.fit(gimg.convert("RGB"), (640, 720), Image.LANCZOS), (0 if gl else 640, 0))
    c.paste(ImageOps.fit(himg.convert("RGB"), (640, 720), Image.LANCZOS), (640 if gl else 0, 0))
    c = ImageEnhance.Contrast(c).enhance(1.15)
    parts = [p.strip().upper() for p in text.split("|") if p.strip()][:2] or ["WATCH THIS"]
    d = ImageDraw.Draw(c)
    y = 190
    for i, p in enumerate(parts):
        size = 150
        while True:
            f = ImageFont.truetype(FONT, size)
            if d.textlength(p, font=f) < W * 0.62 or size < 60:
                break
            size -= 6
        w = d.textlength(p, font=f)
        d.text(((W - w) / 2, y), p, font=f, fill="#FFFFFF" if i == 0 else edit["accent"], stroke_width=10, stroke_fill="black")
        y += size + 20
    c.save(path, quality=92)

# ---------------- upload ----------------
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
    cr = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token",
                     client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                     scopes=["https://www.googleapis.com/auth/youtube.upload"])
    cr.refresh(Request())
    yt = build("youtube", "v3", credentials=cr)
    pa = publish_at()
    status = {"privacyStatus": "private" if pa else "public", "selfDeclaredMadeForKids": False,
              "containsSyntheticMedia": True}
    if pa:
        status["publishAt"] = pa
    body = {"snippet": {"title": meta["title"], "description": meta["description"], "tags": meta["tags"],
                        "categoryId": "27"}, "status": status}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(path, chunksize=-1, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    if thumb:
        try:
            yt.thumbnails().set(videoId=resp["id"], media_body=MediaFileUpload(thumb)).execute()
        except Exception as e:
            print("thumbnail failed:", e)
    print("uploaded", resp["id"], "publishAt", pa)

# ---------------- Friday image post ----------------
def friday_post(state):
    topic, angle = pick_topic(state)
    j = llm_json(f"Topic: {topic}\nAngle: {angle}\nWrite a Friday community post for a psychology channel. JSON keys: "
                 "text (90-120 words, thoughtful, ends with a question to the audience, no links, no sources), "
                 "quote (a short original insight, max 14 words), hashtags (list of 4).")
    bg = txt2img("abstract minimal cinematic illustration, soft light, deep colors, no text, no people", random.randint(1, 10**6))
    bg = ImageEnhance.Brightness(bg.resize((1080, 1080), Image.LANCZOS)).enhance(0.55)
    box = textbox(str(j.get("quote", topic)), 64, "#FFFFFF", 860)
    bg = bg.convert("RGBA")
    bg.paste(box, ((1080 - box.width) // 2, (1080 - box.height) // 2), box)
    day = dt.date.today().isoformat()
    bg.convert("RGB").save(f"posts/{day}.png")
    txt = str(j.get("text", "")) + "\n\n" + " ".join("#" + str(h).lstrip("#") for h in j.get("hashtags", []))
    open(f"posts/{day}.txt", "w").write(re.sub(r"https?://\S+", "", txt))
    state["topics"].append(topic)
    save_state(state)

# ---------------- main ----------------
def main():
    state = load_state()
    if KIND == "post":
        return friday_post(state)
    short = KIND == "short"
    topic, angle = pick_topic(state)
    g = make_guest(topic, state)
    lines = script_short(topic, angle, g) if short else script_long(topic, angle, g)
    if len(lines) < 4:
        raise RuntimeError("script too short")
    edit = make_edit(topic, g, lines)
    meta = make_meta(topic, lines, short)

    pace = edit["pace"]
    voice, tl = build_audio(lines, g, pace)
    if short and tl[-1][2] > 58:
        voice, tl = build_audio(lines, g, max(0.75, pace * 58 / tl[-1][2]))
    mix = np.concatenate([voice, np.zeros(SR, np.float32)])
    mix = mix + music(edit["mood"], len(mix))
    wr("work/mix.wav", mix * 0.95)

    gimg = guest_image(g)
    himg = host_image(g["studio"])
    video = "out/video.mp4"
    render(short, himg, gimg, tl, voice, edit, meta["title"], video)
    thumb = None
    if not short:
        thumb = "out/thumb.jpg"
        thumbnail(himg, gimg, meta["thumb"], edit, thumb)
    json.dump({"topic": topic, "guest": g, "edit": edit, "meta": meta, "lines": lines},
              open("out/info.json", "w"), indent=1)
    if os.getenv("YT_REFRESH_TOKEN"):
        upload(video, meta, thumb)
    state["topics"].append(topic)
    state["guests"].append(g["name"])
    save_state(state)

if __name__ == "__main__":
    main()
