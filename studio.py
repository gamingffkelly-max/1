import os, re, sys, math, wave, random, shutil, subprocess, urllib.request
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from functools import lru_cache
from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor

ORDER = ["CBS", "NBC", "ABC", "PBS"]
COL = {"CBS": (46, 204, 113), "PBS": (231, 60, 60), "NBC": (255, 200, 40), "ABC": (235, 235, 240)}
# one fixed voice per character -> same voice in every video
VOICES = {"CBS": "en/en_US/ryan/medium/en_US-ryan-medium",
          "PBS": "en/en_GB/alan/medium/en_GB-alan-medium",
          "NBC": "en/en_US/amy/medium/en_US-amy-medium",
          "ABC": "en/en_US/joe/medium/en_US-joe-medium"}
RATE = 22050
PAUSE = 0.28
UP = ("rise", "rose", "surge", "rally", "gain", "jump", "soar", "growth", "climb", "opportunit", "upside", "benefit", "peace", "deal", "recover")
DN = ("fall", "fell", "drop", "plunge", "crash", "slump", "decline", "loss", "tumble", "risk", "danger", "harm", "war", "crisis", "threat")
STAT = re.compile(r"(\$\s?\d[\d,.]*(?:\s?(?:trillion|billion|million|thousand))?|\d[\d,.]*\s?(?:%|percent))", re.I)


@lru_cache(maxsize=None)
def font(sz, bold=True):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else "")
    try:
        return ImageFont.truetype(p, max(8, int(sz)))
    except Exception:
        return ImageFont.load_default()


def wrap(txt, f, maxw):
    out, cur = [], ""
    for w in txt.split():
        t = (cur + " " + w).strip()
        if f.getlength(t) <= maxw:
            cur = t
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out


def direction(t):
    l = t.lower()
    u, d = sum(k in l for k in UP), sum(k in l for k in DN)
    return 1 if u > d else -1 if d > u else 0


def base_card(w, h, col):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), radius=int(h * .12), fill=(10, 14, 28, 232),
                                         outline=col + (255,), width=2)
    return im


def stat_card(txt, w, h, col):
    im = base_card(w, h, col)
    d = ImageDraw.Draw(im)
    sz = h * .55
    f = font(sz)
    while f.getlength(txt) > w * .9 and sz > 10:
        sz *= .9
        f = font(sz)
    d.text(((w - f.getlength(txt)) / 2, h * .08), txt, font=f, fill=col + (255,))
    d.text((w * .06, h * .78), "KEY NUMBER", font=font(h * .13), fill=(180, 190, 210, 255))
    return im


def chart_card(w, h, dirn, seed):
    r = random.Random(seed)
    v = [0.0]
    for _ in range(30):
        v.append(v[-1] + 0.12 * dirn + r.uniform(-.35, .35))
    lo, hi = min(v), max(v)
    pts = [(int(w * .06 + w * .88 * i / 30), int(h * .86 - h * .62 * (a - lo) / (hi - lo + 1e-6))) for i, a in enumerate(v)]
    col = (46, 204, 113) if dirn > 0 else (231, 60, 60)
    im = base_card(w, h, col)
    d = ImageDraw.Draw(im)
    d.line(pts, fill=col + (255,), width=max(3, h // 28), joint="curve")
    d.text((int(w * .06), int(h * .04)), "▲ POSITIVE" if dirn > 0 else "▼ NEGATIVE", font=font(h * .18), fill=col + (255,))
    return im


def fade(card, f):
    c = card.copy()
    c.putalpha(c.getchannel("A").point(lambda v: int(v * f)))
    return c


def layout(W, H):
    if W >= H:
        ch, by = int(H * 0.48), int(H * 0.66)
        return {n: (int(W * x), by, ch) for n, x in zip(ORDER, (0.14, 0.38, 0.62, 0.86))}
    ch = int(H * 0.20)
    return {"CBS": (int(W * .27), int(H * .43), ch), "PBS": (int(W * .73), int(H * .43), ch),
            "NBC": (int(W * .27), int(H * .67), ch), "ABC": (int(W * .73), int(H * .67), ch)}


def init(cfg):
    global C, SEAT, TABLE, PLATE, TICK, TICK_W, BADGE, PH, TH
    C = cfg
    W, H = cfg["W"], cfg["H"]
    SEAT = layout(W, H)
    PH = {n: i * 1.7 for i, n in enumerate(ORDER)}
    TH = int(min(W, H) * 0.075)
    TABLE, PLATE = [], {}
    tx0 = int(W * 0.02)
    for by in sorted(set(s[1] for s in SEAT.values())):
        w = int(W * 0.96)
        strip = Image.new("RGBA", (w, TH), (0, 0, 0, 0))
        sd = ImageDraw.Draw(strip)
        sd.rounded_rectangle((0, 0, w - 1, TH - 1), radius=int(TH * .35), fill=(96, 62, 40, 255))
        sd.rectangle((10, 4, w - 11, 8), fill=(130, 90, 62, 255))
        ty = by - int(TH * 0.2)
        for n, (cx, b, _) in SEAT.items():
            if b != by:
                continue
            nf = font(TH * 0.42)
            tw = nf.getlength(n)
            cl = cx - tx0
            x0, y0, x1, y1 = cl - tw / 2 - 14, TH * .30, cl + tw / 2 + 14, TH * .88
            sd.rounded_rectangle((x0, y0, x1, y1), radius=8, fill=(20, 24, 38, 255), outline=COL[n], width=2)
            sd.text((cl - tw / 2, TH * .34), n, font=nf, fill=COL[n])
            PLATE[n] = (x0 + tx0, y0 + ty, x1 + tx0, y1 + ty)
        TABLE.append((strip, tx0, ty))
    hb = int(H * 0.045) if W >= H else int(H * 0.03)
    f = font(hb * 0.55)
    unit = "   •   " + cfg["topic"].upper()[:90] + "   •   LIVE WORLD NEWS DEBATE   •   CBS vs PBS   "
    uw = int(f.getlength(unit)) + 1
    reps = int(W * 2 / uw) + 3
    TICK = Image.new("RGB", (uw * reps, hb), (14, 18, 32))
    ImageDraw.Draw(TICK).text((0, hb * 0.18), unit * reps, font=f, fill=(240, 240, 240))
    TICK_W = uw
    BADGE = Image.new("RGBA", (int(hb * 2.4), int(hb * 0.8)), (0, 0, 0, 0))
    bd = ImageDraw.Draw(BADGE)
    bd.rounded_rectangle((0, 0, BADGE.width - 1, BADGE.height - 1), radius=6, fill=(220, 30, 40, 255))
    bd.text((int(hb * .35), int(hb * .08)), "LIVE", font=font(hb * 0.55), fill=(255, 255, 255, 255))


def render_scene(sc):
    W, H, fps = C["W"], C["H"], C["fps"]
    x = build_extras(sc)
    out = f"{C['tmp']}/v{sc['i']:05d}.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "ultrafast", "-tune", "animation",
           "-crf", "26", "-pix_fmt", "yuv420p", "-an", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for k in range(sc["n"]):
        p.stdin.write(draw_frame(sc, k, x).convert("RGB").tobytes())
    p.stdin.close()
    p.wait()
    return out


def voice_path(who):
    sub = VOICES[who]
    name = sub.split("/")[-1]
    os.makedirs("voices", exist_ok=True)
    for ext in (".onnx", ".onnx.json"):
        p = f"voices/{name}{ext}"
        if not os.path.exists(p):
            urllib.request.urlretrieve(f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{sub}{ext}", p)
    return f"voices/{name}.onnx"


def tts(who, text, out):
    r = subprocess.run([sys.executable, "-m", "piper", "--model", voice_path(who), "--output_file", out],
                       input=text.encode(), capture_output=True)
    if r.returncode or not os.path.exists(out):
        raise RuntimeError("piper failed: " + r.stderr.decode()[-300:])


def readwav(p):
    w = wave.open(p)
    r = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    w.close()
    if r != RATE and len(x):
        x = np.interp(np.linspace(0, len(x) - 1, int(len(x) * RATE / r)), np.arange(len(x)), x)
    return x.astype(np.float32)


def to_scenes(lines, sources, maxw=24):
    sc = []
    for ln in lines:
        tags = re.findall(r"\[S(\d+)\]", ln["text"])
        src = None
        if tags and 0 <= int(tags[0]) - 1 < len(sources):
            src = sources[int(tags[0]) - 1]
        clean = re.sub(r"\s*\[S\d+\]", "", ln["text"]).strip()
        chunks, cur = [], ""
        for s in re.split(r"(?<=[.!?])\s+", clean):
            if cur and len((cur + " " + s).split()) > maxw:
                chunks.append(cur)
                cur = s
            else:
                cur = (cur + " " + s).strip()
        if cur:
            chunks.append(cur)
        for c in chunks:
            sc.append({"who": ln["who"], "text": c, "src": src})
    for i, s in enumerate(sc):
        s["i"] = i
    return sc


def produce(lines, sources, topic, W, H, fps, out, max_sec=None, tmp="work"):
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    scenes = to_scenes(lines, sources)
    for w in VOICES:
        voice_path(w)

    def job(s):
        s["wav"] = f"{tmp}/a{s['i']:05d}.wav"
        tts(s["who"], s["text"], s["wav"])

    print("voices:", len(scenes), "scenes", flush=True)
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(job, scenes))
    data = [readwav(s["wav"]) for s in scenes]
    if max_sec:
        tot, keep = 0, 0
        for x in data:
            tot += len(x) / RATE + PAUSE
            if tot > max_sec and keep >= 4:
                break
            keep += 1
        scenes, data = scenes[:keep], data[:keep]
    t0, chunks = 0.0, []
    for s, x in zip(scenes, data):
        n = int(math.ceil((len(x) / RATE + PAUSE) * fps))
        tgt = int(round(n / fps * RATE))
        a = np.zeros(tgt, dtype=np.float32)
        a[:min(len(x), tgt)] = x[:tgt]
        chunks.append(a.astype(np.int16))
        step = RATE / fps
        e = np.array([float(np.sqrt(np.mean(x[int(k * step):int((k + 1) * step)] ** 2))) if len(x[int(k * step):int((k + 1) * step)]) else 0.0
                      for k in range(n)])
        e = np.clip(e / (np.percentile(e, 90) + 1e-6), 0, 1)
        e = np.convolve(e, [.25, .5, .25], mode="same")
        s.update(n=n, t0=t0, env=e.tolist())
        t0 += n / fps
    master = f"{tmp}/master.wav"
    wv = wave.open(master, "wb")
    wv.setnchannels(1)
    wv.setsampwidth(2)
    wv.setframerate(RATE)
    wv.writeframes(np.concatenate(chunks).tobytes())
    wv.close()
    del data, chunks
    print(f"total length {t0/60:.1f} min -> rendering", flush=True)
    init({"W": W, "H": H, "fps": fps, "topic": topic, "tmp": tmp})
    clips = []
    with Pool(os.cpu_count() or 2) as pool:
        for j, c in enumerate(pool.imap(render_scene, scenes, chunksize=1)):
            clips.append(c)
            if j % 25 == 0:
                print("rendered", j, "/", len(scenes), flush=True)
    lst = f"{tmp}/list.txt"
    open(lst, "w").write("".join(f"file '{os.path.abspath(c)}'\n" for c in clips))
    vid = f"{tmp}/video.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", vid], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", vid, "-i", master, "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "160k", "-shortest", "-movflags", "+faststart", out], check=True)
    for c in clips:
        os.remove(c)
    return out
