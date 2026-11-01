import os, re, math, json, wave, zlib, random, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import studio as S
import rig as R

SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
ROLE = {"CBS": "BENEFITS & UPSIDE", "PBS": "RISKS & DOWNSIDE", "NBC": "DEEP QUESTIONS", "ABC": "HOST"}
CAP = []


def sfont(sz):
    try:
        return ImageFont.truetype(SERIF, int(max(8, sz)))
    except Exception:
        return S.font(sz)


# ======================= STUDIO LOOK / LIGHTING =======================
def studio_bg(W, H, seed, chairs=None):
    r = random.Random(seed)
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(54 - 28 * t), int(37 - 17 * t), int(27 - 9 * t)))
    n = 4 if W >= H else 3
    for i in range(n):
        x = int(W * (0.06 + 0.24 * i)) if W >= H else int(W * (0.05 + 0.32 * i))
        w = int(W * 0.17) if W >= H else int(W * 0.28)
        y, h = int(H * 0.10), int(H * 0.22) if W >= H else int(H * 0.12)
        d.rectangle((x, y, x + w, y + h), fill=(20, 22, 30), outline=(125, 92, 55), width=3)
        pts = [(x + w * 0.08 + w * 0.84 * j / 8, y + h * (0.75 - 0.5 * j / 8 + r.uniform(-.12, .12))) for j in range(9)]
        d.line(pts, fill=(255, 190, 70), width=max(2, w // 50))
    bok = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bok)
    for _ in range(26):
        x, y, rr = r.randrange(W), r.randrange(int(H * 0.55)), r.randrange(int(H * 0.02), int(H * 0.06))
        bd.ellipse((x - rr, y - rr, x + rr, y + rr), fill=r.choice([(255, 170, 60), (255, 120, 40), (90, 170, 255), (255, 220, 140)]) + (70,))
    im = Image.alpha_composite(im.convert("RGBA"), bok.filter(ImageFilter.GaussianBlur(5))).convert("RGB")
    if chairs:
        d = ImageDraw.Draw(im)
        for n_, (cx, by, ch) in chairs.items():
            cw = ch * 0.40
            d.rounded_rectangle((cx - cw, by - ch * 0.78, cx + cw, by + S.TH), radius=30, fill=(26, 22, 30))
    return im


def make_overlays(W, H):
    yy, xx = np.mgrid[0:H, 0:W]
    rr = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    a = np.clip((rr - 0.55) / 0.75, 0, 1) ** 1.6 * 170
    a = np.maximum(a, np.clip((yy / H - 0.62) / 0.38, 0, 1) * 150)
    vig = Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), a.astype(np.uint8)]), "RGBA")
    glow = {}
    rg = np.sqrt(((xx - W / 2) / (W * 0.55)) ** 2 + ((yy - H * 0.42) / (H * 0.55)) ** 2)
    ag = (np.clip(1 - rg, 0, 1) ** 2 * 95).astype(np.uint8)
    for nm in S.ORDER:
        c = S.COL[nm]
        glow[nm] = Image.fromarray(np.dstack([np.full((H, W), c[0], np.uint8), np.full((H, W), c[1], np.uint8),
                                              np.full((H, W), c[2], np.uint8), ag]), "RGBA")
    sw = int(W * 0.18)
    g = (np.exp(-((np.arange(sw) - sw / 2) / (sw * 0.22)) ** 2) * 30).astype(np.uint8)
    sweep = Image.fromarray(np.dstack([np.full((int(H * 1.4), sw), 255, np.uint8)] * 3 + [np.tile(g, (int(H * 1.4), 1))]), "RGBA")
    sweep = sweep.rotate(16, expand=True, resample=Image.BICUBIC)
    bw = int(W * 0.22)
    gb = np.concatenate([np.linspace(0, 1, 14), np.ones(bw - 28), np.linspace(1, 0, 14)])
    band = np.zeros((H, bw, 4), np.uint8)
    band[..., 0], band[..., 1], band[..., 2] = 236, 228, 208
    band[..., 3] = (np.tile(gb, (H, 1)) * 238).astype(np.uint8)
    for y in range(0, H, max(40, H // 12)):
        band[y:y + 2, :, :3] = 200
    return vig, glow, sweep, Image.fromarray(band, "RGBA")


def mic_overlay(W, H):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    mx, my = int(W * (0.66 if W >= H else 0.70)), int(H * (0.70 if W >= H else 0.78))
    s = int(min(W, H) * 0.07)
    d.line([(int(W * 0.9), H), (mx, my + s)], fill=(40, 40, 46, 255), width=max(6, s // 3))
    d.rounded_rectangle((mx - s // 2, my - s, mx + s // 2, my + s), radius=s // 2, fill=(18, 18, 22, 255), outline=(120, 120, 130, 255), width=max(2, s // 10))
    for k in range(-3, 4):
        d.line([(mx - s // 2 + 4, my + k * s // 4), (mx + s // 2 - 4, my + k * s // 4)], fill=(60, 60, 66, 255), width=2)
    d.rectangle((0, int(H * 0.93), W, H), fill=(22, 16, 12, 255))
    return im


def name_card(nm, W, H):
    fs = int(H * 0.05) if W >= H else int(W * 0.075)
    f, f2 = S.font(fs), S.font(fs * 0.42)
    w = int(max(f.getlength(nm), f2.getlength(ROLE[nm]))) + 80
    h = int(fs * 2.0)
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text(((w - f.getlength(nm)) / 2, 2), nm, font=f, fill=S.COL[nm] + (255,))
    glow = lay.filter(ImageFilter.GaussianBlur(fs * 0.25))
    back = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(back).rounded_rectangle((0, 0, w - 1, h - 1), radius=14, fill=(0, 0, 0, 120))
    out = Image.alpha_composite(Image.alpha_composite(back, glow), glow)
    d = ImageDraw.Draw(out)
    d.text(((w - f.getlength(nm)) / 2, 2), nm, font=f, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
    d.text(((w - f2.getlength(ROLE[nm])) / 2, fs * 1.25), ROLE[nm], font=f2, fill=S.COL[nm] + (255,), stroke_width=1, stroke_fill=(0, 0, 0, 255))
    return out


def init2(cfg):
    S._init_prev(cfg)
    global BGW, BGC, VIG, GLOW, SWEEP, BAND, MIC, CLOSE, NAME
    W, H = cfg["W"], cfg["H"]
    BGW = studio_bg(W, H, 7, S.SEAT)
    BGC = studio_bg(W, H, 7).filter(ImageFilter.GaussianBlur(7))
    VIG, GLOW, SWEEP, BAND = make_overlays(W, H)
    MIC = mic_overlay(W, H)
    hw = 0.2 * W if W >= H else 0.46 * W
    CLOSE = {n: R.Rig(n, int(540 * hw / 210)) for n in S.ORDER}
    NAME = {n: name_card(n, W, H) for n in S.ORDER}


# ======================= CARDS: PAPER EVIDENCE, CAPTIONS =======================
def paper_card(info, w):
    r = random.Random(zlib.crc32(info["title"].encode()))
    p = int(w * 0.06)
    f1, f2, f3 = sfont(w * 0.085), sfont(w * 0.052), sfont(w * 0.064)
    head = S.wrap(info["title"], f3, w - 2 * p)[:4]
    h = int(p * 3.4 + w * 0.085 + w * 0.06 + len(head) * w * 0.078 + p)
    m = int(w * 0.07)
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask = Image.new("L", (w, h), 0)
    jag = [(0, 0), (w, 0)] + [(w - i * w / 24, h - 5 + r.randrange(0, 6)) for i in range(0, 25)]
    ImageDraw.Draw(mask).polygon(jag, fill=255)
    arr = np.full((h, w, 3), (238, 231, 212), np.float32) + np.random.RandomState(1).normal(0, 4, (h, w, 1))
    arr[::7, :, :] -= 6
    paper = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    card.paste(paper, (0, 0), mask)
    d = ImageDraw.Draw(card)
    y = p
    d.text((p, y), info["name"].upper(), font=f1, fill=(20, 20, 20, 255))
    y += int(w * 0.11)
    d.line([(p, y), (w - p, y)], fill=(40, 40, 40, 255), width=3)
    y += int(w * 0.025)
    d.text((p, y), "PUBLISHED: " + info["date"].upper(), font=f2, fill=(90, 30, 30, 255))
    y += int(w * 0.08)
    for l in head:
        d.text((p, y), l, font=f3, fill=(35, 35, 35, 255))
        y += int(w * 0.078)
    st = Image.new("RGBA", (int(w * 0.34), int(w * 0.1)), (0, 0, 0, 0))
    sd = ImageDraw.Draw(st)
    sd.rounded_rectangle((0, 0, st.width - 1, st.height - 1), radius=8, outline=(200, 30, 30, 230), width=4)
    sd.text((st.width * 0.1, st.height * 0.14), "SOURCE", font=S.font(st.height * 0.6), fill=(200, 30, 30, 230))
    st = st.rotate(10, expand=True, resample=Image.BICUBIC)
    card.alpha_composite(st, (w - st.width - 4, h - st.height - 10))
    tape = Image.new("RGBA", (int(w * 0.3), int(w * 0.07)), (255, 225, 90, 150)).rotate(-4, expand=True)
    card.alpha_composite(tape, (int(w * 0.35), 0))
    canvas = Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0))
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, 150), (m + 8, m + 12, m + 8 + w, m + 12 + h), mask=None)
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
    canvas.alpha_composite(card, (m, m))
    return canvas


def build_words(sc):
    W, H, fps = S.C["W"], S.C["H"], S.C["fps"]
    fs = int(H * 0.046) if W >= H else int(W * 0.052)
    f, sw, sp = S.font(fs), max(2, fs // 9), int(fs * 0.3)
    words = sc["text"].split()
    items = []
    for w in words:
        lw = re.sub(r"[^\w%$.]", "", w).lower()
        col = (255, 255, 255)
        if re.search(r"\d", lw):
            col = (255, 205, 50)
        elif any(k in lw for k in S.UP):
            col = (70, 225, 130)
        elif any(k in lw for k in S.DN):
            col = (255, 75, 75)
        iw, ih = int(f.getlength(w)) + 2 * sw + 4, int(fs * 1.4)
        im = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((sw, sw), w, font=f, fill=col + (255,), stroke_width=sw, stroke_fill=(0, 0, 0, 255))
        items.append((im, len(w)))
    lines, cur = [[]], 0
    for it in items:
        if cur + it[0].width > W * 0.88 and lines[-1]:
            lines.append([])
            cur = 0
        lines[-1].append(it)
        cur += it[0].width + sp
    lh = int(fs * 1.3)
    y0 = int(H * (0.93 if W >= H else 0.90)) - len(lines) * lh
    tot = sum(i[1] for i in items) or 1
    tend = max(0.6, sc["n"] / fps - 0.35) * 0.97
    out, acc = [], 0
    for li, ln in enumerate(lines):
        x = int((W - (sum(i[0].width + sp for i in ln) - sp)) / 2)
        for im, c in ln:
            out.append((im, x, y0 + li * lh, tend * acc / tot))
            x += im.width + sp
            acc += c
    return out


def build_extras(sc):
    W, H = S.C["W"], S.C["H"]
    i = sc["i"]
    r = random.Random(i * 7919)
    x = {"amp": r.uniform(.7, 1.3), "lean": r.choice([-2, -1, 0, 1, 2]), "shot": "single" if (W < H or i % 6) else "wide"}
    x["z0"], x["z1"] = (1.0, 1.06) if i % 2 else (1.06, 1.0)
    x["words"] = build_words(sc)
    d, m = S.direction(sc["text"]), S.STAT.search(sc["text"])
    if W >= H:
        zs, zc, px, py, pw = (int(.03 * W), int(.08 * H), int(.20 * W), int(.13 * H)), (int(.03 * W), int(.25 * H), int(.22 * W), int(.16 * H)), int(.64 * W), int(.10 * H), int(.27 * W if x["shot"] == "wide" else .33 * W)
    else:
        zs, zc, px, py, pw = (int(.04 * W), int(.04 * H), int(.44 * W), int(.06 * H)), (int(.52 * W), int(.04 * H), int(.44 * W), int(.06 * H)), int(.19 * W), int(.115 * H), int(.62 * W)
    x["stat"] = x["chart"] = x["paper"] = None
    if m:
        col = (46, 204, 113) if d > 0 else (231, 60, 60) if d < 0 else (255, 200, 40)
        x["stat"] = (S.stat_card(m.group(1).strip(" .,"), zs[2], zs[3], col), zs[0], zs[1])
    if d and i % 3 == 0:
        x["chart"] = (S.chart_card(zc[2], zc[3], d, i), zc[0], zc[1])
    if sc.get("src"):
        x["paper"] = (paper_card(sc["src"], pw), px, py)
    return x


# ======================= FRAME =======================
def draw_frame(sc, k, x):
    W, H, fps = S.C["W"], S.C["H"], S.C["fps"]
    t = k / fps
    T = sc["t0"] + t
    spk = sc["who"]
    e = sc["env"][min(k, len(sc["env"]) - 1)]
    changed = sc.get("prev") != spk
    ease = min(1.0, t / 0.35) if changed else 1.0
    ease = ease * ease * (3 - 2 * ease)
    if x["shot"] == "wide":
        img = BGW.copy()
        for nm in [n for n in S.ORDER if n != spk] + [spk]:
            cx, by, ch = S.SEAT[nm]
            ph = S.PH[nm]
            if nm == spk:
                dy = -(2 + 5 * e) * x["amp"] - 1.5 * math.sin(T * 8.2 + ph)
                ang, look = x["lean"] * 0.5 + 0.8 * math.sin(T * 2 + ph), 2 * math.sin(T * 0.7)
            else:
                dy, ang = -2 * math.sin(T * 3.1 + ph), 0.8 * math.sin(T * 1.9 + ph)
                look = 7 if S.SEAT[spk][0] > cx else -7
            im = S.SPR[nm].frame(T, nm == spk, e if nm == spk else 0.0, nm, look, ph, ease)
            im = im.rotate(ang, resample=Image.BICUBIC, expand=True)
            img.paste(im, (int(cx - im.width / 2), int(by + S.TH * .35 - im.height + dy)), im)
        for strip, tx, ty in S.TABLE:
            img.paste(strip, (tx, ty), strip)
        ImageDraw.Draw(img).rounded_rectangle(S.PLATE[spk], radius=10, outline=S.COL[spk], width=4)
    else:
        img = BGC.copy()
        img.paste(GLOW[spk], (0, 0), GLOW[spk])
        rg = CLOSE[spk]
        ph = S.PH[spk]
        im = rg.frame(T, True, e, spk, 2 * math.sin(T * 0.7), ph, ease)
        im = im.rotate(x["lean"] * 0.4 + 0.6 * math.sin(T * 2 + ph), resample=Image.BICUBIC)
        dy = -(2 + 5 * e) * x["amp"] * rg.sc - 1.5 * math.sin(T * 8.2 + ph)
        img.paste(im, (int(W / 2 - (R.OX + 200) * rg.sc), int(H * (0.40 if W >= H else 0.47) - 150 * rg.sc + dy)), im)
        img.paste(MIC, (0, 0), MIC)
    z = x["z0"] + (x["z1"] - x["z0"]) * k / max(1, sc["n"] - 1)
    if changed:
        z *= 1 + 0.05 * max(0, 1 - t / 0.18)
    if z > 1.001:
        cw, chh = W / z, H / z
        x0, y0 = (W - cw) / 2, (H * 0.50 - chh / 2) if x["shot"] != "wide" else (H - chh) / 2
        y0 = min(max(y0, 0), H - chh)
        img = img.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + chh))
    sx = int(((T * 0.05) % 1.6 - 0.4) * W)
    img.paste(SWEEP, (sx, -int(H * 0.2)), SWEEP)
    img.paste(VIG, (0, 0), VIG)
    off = int(T * 90) % S.TICK_W
    img.paste(S.TICK.crop((off, 0, off + W, S.TICK.height)), (0, 0))
    img.paste(S.BADGE, (8, 3), S.BADGE)
    if x["stat"]:
        c, px, py = x["stat"]
        f = min(1, t / 0.35)
        cc = c if f >= 1 else S.fade(c, f)
        img.paste(cc, (px, py + int((1 - f) * 20)), cc)
    if x["chart"]:
        c, px, py = x["chart"]
        part = c.crop((0, 0, max(2, int(c.width * min(1, t / 1.3))), c.height))
        img.paste(part, (px, py), part)
    if x["paper"]:
        c, px, py = x["paper"]
        p = min(1.0, t / 0.55)
        eb = 1 + 2.70158 * (p - 1) ** 3 + 1.70158 * (p - 1) ** 2
        ang = 14 * (1 - eb) - 2.5 + 0.8 * math.sin(T * 1.3)
        pc = c.rotate(ang, expand=True, resample=Image.BICUBIC)
        s = 0.7 + 0.3 * min(1.0, eb)
        if s < 0.999:
            pc = pc.resize((int(pc.width * s), int(pc.height * s)), Image.BILINEAR)
        ee = 1 - (1 - p) ** 3
        img.paste(pc, (int(px + c.width / 2 - pc.width / 2 + (1 - ee) * W * 0.4), int(py + c.height / 2 - pc.height / 2 - (1 - ee) * H * 0.1)), pc)
    if x["shot"] != "wide":
        nc = NAME[spk]
        img.paste(nc, (int((W - nc.width) / 2), int(H * (0.63 if W >= H else 0.62))), nc)
    for im, wx, wy, rt in x["words"]:
        if t < rt:
            continue
        a = t - rt
        if a < 0.14:
            s = 1 + 0.35 * (1 - a / 0.14)
            w2, h2 = int(im.width * s), int(im.height * s)
            im2 = im.resize((w2, h2))
            img.paste(im2, (wx - (w2 - im.width) // 2, wy - (h2 - im.height) // 2), im2)
        else:
            img.paste(im, (wx, wy), im)
    if changed and t < 0.28:
        bx = int(-BAND.width + (W + BAND.width) * min(1, t / 0.28))
        img.paste(BAND, (bx, 0), BAND)
    return img


# ======================= MUSIC + SOUND EFFECTS =======================
RATE = 22050


def music_loop():
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (261.63, 329.63, 392.0), (196.0, 246.94, 293.66)]
    beat = 60 / 72
    seg = int(4 * beat * RATE)
    t = np.arange(seg) / RATE
    env = np.minimum(1, t / 0.6) * np.minimum(1, (seg / RATE - t) / 0.6)
    out = []
    rs = np.random.RandomState(3)
    for ch in chords:
        pad = sum(np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2 * f * t) for f in ch) * env * 0.18
        bass = np.sin(2 * np.pi * ch[0] / 2 * t) * env * 0.35
        arp = np.zeros(seg)
        for j in range(8):
            s0 = int(j * beat / 2 * RATE)
            n = min(int(0.45 * RATE), seg - s0)
            tt = np.arange(n) / RATE
            arp[s0:s0 + n] += np.sin(2 * np.pi * ch[j % 3] * 2 * tt) * np.exp(-tt * 7) * 0.25
        for j in range(4):
            s0 = int(j * beat * RATE)
            n = min(int(0.05 * RATE), seg - s0)
            arp[s0:s0 + n] += rs.randn(n) * np.exp(-np.arange(n) / (0.01 * RATE)) * 0.04
        out.append(pad + bass + arp)
    m = np.concatenate(out)
    return (m / (np.abs(m).max() + 1e-6) * 0.5).astype(np.float32)


def sfx():
    rs = np.random.RandomState(5)
    n = int(0.3 * RATE)
    x = np.arange(n) / n
    wh = np.convolve(rs.randn(n), np.ones(8) / 8, mode="same") * np.sin(np.pi * x) ** 2 * 0.5
    n2 = int(0.45 * RATE)
    t2 = np.arange(n2) / RATE
    ding = (np.sin(2 * np.pi * 1568 * t2) + 0.4 * np.sin(2 * np.pi * 3136 * t2)) * np.exp(-t2 * 9) * 0.22
    n3 = int(0.2 * RATE)
    pp = np.diff(rs.randn(n3 + 1)) * np.abs(np.sin(np.arange(n3) / n3 * np.pi * 5)) * np.exp(-np.arange(n3) / (0.09 * RATE)) * 0.35
    return wh.astype(np.float32), ding.astype(np.float32), pp.astype(np.float32)


def mix(master, out, scenes):
    wh, ding, pp = sfx()
    ml = music_loop()
    L = len(ml)
    ev = []
    for s in scenes:
        t0 = int(s["t0"] * RATE)
        if s.get("prev") != s["who"]:
            ev.append((t0, wh))
        if s.get("src"):
            ev.append((t0 + int(.05 * RATE), pp))
        if S.STAT.search(s["text"]):
            ev.append((t0 + int(.12 * RATE), ding))
    ev.sort(key=lambda e: e[0])
    w = wave.open(master)
    N = w.getnframes()
    wo = wave.open(out, "wb")
    wo.setnchannels(1)
    wo.setsampwidth(2)
    wo.setframerate(RATE)
    pos, CH = 0, RATE * 30
    while pos < N:
        n = min(CH, N - pos)
        v = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
        m = ml[np.arange(pos, pos + n) % L]
        env = np.convolve(np.abs(v), np.ones(2205) / 2205, mode="same")
        g = np.convolve(1 - 0.6 * np.clip(env / 0.08, 0, 1), np.ones(4410) / 4410, mode="same")
        y = v + 0.16 * m * g
        for s0, a in ev:
            if s0 >= pos + n:
                break
            lo, hi = max(s0, pos), min(s0 + len(a), pos + n)
            if hi > lo:
                y[lo - pos:hi - pos] += a[lo - s0:hi - s0]
        wo.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
        pos += n
    wo.close()
    w.close()


# ======================= THUMBNAILS (designed by local AI, varied) =======================
PAL = [(255, 70, 60), (255, 200, 0), (0, 215, 150), (70, 160, 255), (255, 125, 0), (190, 90, 255)]
STOPW = set("the a an of to in on for and or is are was be how why what will with from this that your can".split())


def hexrgb(s):
    try:
        s = s.strip("# ")
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return None


def thumb_spec(title, r, seed):
    spec = {}
    try:
        import brain
        t = brain.llm('Design a YouTube thumbnail for a world news debate video titled: "' + title + '".\nReply with ONLY JSON: {"headline":"2-5 punchy words, no channel name","highlight":"one word from the headline","layout":"versus|center|shock|quad|paper","badge":"short like BREAKING, ??, VS or a number","mood":"fear|hope|shock|calm","accent":"#RRGGBB"}',
                      system="You are a viral thumbnail designer. Output JSON only.", tokens=160, temp=0.9)
        spec = json.loads(re.search(r"\{.*\}", t, re.S).group(0))
    except Exception:
        spec = {}
    lay = ["versus", "center", "shock", "quad", "paper"]
    if spec.get("layout") not in lay or r.random() < 0.6:
        spec["layout"] = lay[seed % 5]
    ws = [w for w in re.sub(r"[^\w%$?! -]", "", re.sub(r"#\w+", "", title)).split() if w.lower() not in STOPW]
    hl = re.sub(r"[^\w%$?!-]", " ", str(spec.get("headline", ""))).split()
    spec["headline"] = " ".join(hl[:5] if len(hl) >= 2 else ws[:4]).upper() or "WORLD NEWS DEBATE"
    words = spec["headline"].split()
    if str(spec.get("highlight", "")).upper() not in words:
        spec["highlight"] = max(words, key=len)
    spec["badge"] = str(spec.get("badge") or r.choice(["VS", "??", "!!"]))[:8].upper()
    if spec.get("mood") not in ("fear", "hope", "shock", "calm"):
        spec["mood"] = r.choice(["fear", "hope", "shock"])
    return spec


def face(nm, h, emo="calm"):
    sp = emo == "shock"
    im = R.Rig(nm, int(h / 0.62)).frame(2.0 if sp else 1.0, sp, 0.9 if sp else 0.0, nm, 0, 0.0)
    im = im.crop((0, 0, im.width, int(im.height * 0.62)))
    bb = im.getchannel("A").getbbox()
    return im.crop(bb) if bb else im


def put(base, im, cx, bottom, h, outline=(255, 255, 255)):
    s = h / im.height
    im = im.resize((max(1, int(im.width * s)), int(h)), Image.LANCZOS)
    p = 9
    c = Image.new("RGBA", (im.width + 2 * p, im.height + 2 * p), (0, 0, 0, 0))
    c.paste(im, (p, p))
    if outline:
        o = Image.new("RGBA", c.size, outline + (255,))
        o.putalpha(c.getchannel("A").filter(ImageFilter.MaxFilter(15)))
        base.paste(o, (int(cx - c.width / 2), int(bottom - c.height + p)), o)
    base.paste(c, (int(cx - c.width / 2), int(bottom - c.height + p)), c)


def fit_text(d, text, box, hl, acc, maxl=3, serif=False, color=(255, 255, 255), stroke=8, top=150):
    x0, y0, x1, y1 = box
    for sz in range(top, 36, -6):
        f = sfont(sz) if serif else S.font(sz)
        ls = S.wrap(text, f, x1 - x0)
        if len(ls) <= maxl and len(ls) * sz * 1.08 <= y1 - y0:
            break
    y = y0 + ((y1 - y0) - len(ls) * sz * 1.08) / 2
    for l in ls:
        ws = l.split()
        wl = [f.getlength(w) for w in ws]
        sp = f.getlength(" ")
        x = x0 + ((x1 - x0) - (sum(wl) + sp * (len(ws) - 1))) / 2
        for w, wd in zip(ws, wl):
            hit = hl and re.sub(r"\W", "", w).upper() == re.sub(r"\W", "", hl).upper()
            d.text((x, y), w, font=f, fill=acc if hit else color, stroke_width=stroke, stroke_fill=(0, 0, 0))
            x += wd + sp
        y += sz * 1.08


def tbg(W, H, acc, r):
    base = tuple(int(12 + c * 0.12) for c in acc)
    im = Image.new("RGB", (W, H), base)
    d = ImageDraw.Draw(im)
    st = r.randrange(4)
    mid = tuple(int(b * 0.7 + a * 0.3) for a, b in zip(acc, base))
    if st == 0:
        for i in range(40, 0, -1):
            t = i / 40
            c = tuple(int(base[j] + (acc[j] * 0.55 - base[j]) * (1 - t) ** 2) for j in range(3))
            d.ellipse((W / 2 - W * .8 * t, H / 2 - W * .8 * t, W / 2 + W * .8 * t, H / 2 + W * .8 * t), fill=c)
    elif st == 1:
        for x in range(-H, W, 90):
            d.polygon([(x, 0), (x + 45, 0), (x + 45 - H * .5, H), (x - H * .5, H)], fill=mid)
    elif st == 2:
        cx = W * r.uniform(.3, .7)
        for a in range(0, 360, 24):
            p1, p2 = math.radians(a), math.radians(a + 12)
            d.polygon([(cx, H * .5), (cx + 2 * W * math.cos(p1), H * .5 + 2 * W * math.sin(p1)), (cx + 2 * W * math.cos(p2), H * .5 + 2 * W * math.sin(p2))], fill=mid)
    else:
        for x in range(0, W, 64):
            d.line([(x, 0), (x, H)], fill=(40, 48, 70), width=2)
        for y in range(0, H, 64):
            d.line([(0, y), (W, y)], fill=(40, 48, 70), width=2)
    return im


def badge(d, cx, cy, rad, txt, col):
    d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=col, outline=(0, 0, 0), width=6)
    f = S.font(rad * 0.9)
    while f.getlength(txt) > rad * 1.7:
        f = S.font(f.size * 0.9)
    d.text((cx - f.getlength(txt) / 2, cy - f.size * 0.6), txt, font=f, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))


def emo_for(sp, nm):
    m = sp["mood"]
    return "shock" if (m == "shock" or (m == "fear" and nm == "PBS") or (m == "hope" and nm == "CBS")) else "calm"


def lay_versus(im, d, W, H, sp, acc, r):
    sk = r.randrange(-60, 60)
    d.polygon([(0, 0), (int(W * .56) + sk, 0), (int(W * .44) + sk, H), (0, H)], fill=(18, 96, 52))
    d.polygon([(int(W * .56) + sk, 0), (W, 0), (W, H), (int(W * .44) + sk, H)], fill=(112, 24, 36))
    h = int(H * r.uniform(.72, .82))
    put(im, face("CBS", h, emo_for(sp, "CBS")), int(W * .20), H, h)
    put(im, face("PBS", h, emo_for(sp, "PBS")), int(W * .80), H, h)
    badge(d, W // 2 + sk // 2, int(H * .64), int(H * .14), sp["badge"], acc)
    fit_text(d, sp["headline"], (int(W * .04), int(H * .02), int(W * .96), int(H * .32)), sp["highlight"], acc, maxl=2)


def lay_center(im, d, W, H, sp, acc, r):
    other = "PBS" if sp["mood"] in ("fear", "shock") else "CBS"
    h = int(H * .78)
    put(im, face("NBC", h, "calm"), int(W * .14), H, h)
    put(im, face(other, h, emo_for(sp, other)), int(W * .86), H, h)
    fit_text(d, sp["headline"], (int(W * .27), int(H * .06), int(W * .73), int(H * .94)), sp["highlight"], acc, maxl=4)


def lay_shock(im, d, W, H, sp, acc, r):
    down = sp["mood"] != "hope"
    col = (235, 60, 60) if down else (50, 220, 120)
    pts = [(int(W * (.04 + .52 * i / 7)), int(H * ((.22 + .5 * i / 7) if down else (.72 - .5 * i / 7)) + r.randrange(-30, 30))) for i in range(8)]
    d.line(pts, fill=col, width=22, joint="curve")
    d.polygon([(pts[-1][0] + 40, pts[-1][1] + (30 if down else -30)), (pts[-1][0] - 20, pts[-1][1] - 30), (pts[-1][0] + 10, pts[-1][1] + 40)], fill=col)
    fit_text(d, sp["badge"] if sp["badge"] not in ("VS",) else "??", (int(W * .03), int(H * .10), int(W * .54), int(H * .60)), "", acc, maxl=1, top=260, stroke=12, color=acc)
    fit_text(d, sp["headline"], (int(W * .03), int(H * .64), int(W * .54), int(H * .97)), sp["highlight"], acc, maxl=2)
    nm = "PBS" if down else "CBS"
    put(im, face(nm, int(H * .84), "shock"), int(W * .83), H, int(H * .84))


def lay_quad(im, d, W, H, sp, acc, r):
    h = int(H * .50)
    order = S.ORDER[:]
    r.shuffle(order)
    for nm, fx in zip(order, (.125, .375, .625, .875)):
        put(im, face(nm, h, emo_for(sp, nm)), int(W * fx), H, h)
    for _ in range(3):
        d.text((r.randrange(int(W * .1), int(W * .9)), int(H * .38)), "?", font=S.font(120), fill=acc, stroke_width=6, stroke_fill=(0, 0, 0))
    fit_text(d, sp["headline"], (int(W * .04), int(H * .02), int(W * .96), int(H * .40)), sp["highlight"], acc, maxl=2)


def lay_paper(im, d, W, H, sp, acc, r):
    im.paste((226, 218, 196), (0, 0, W, H))
    for y in range(int(H * .5), H, 22):
        d.rectangle((r.randrange(0, 80), y, W - r.randrange(0, 80), y + 8), fill=(205, 198, 178))
    strip = Image.new("RGBA", (int(W * .92), int(H * .46)), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip)
    sd.polygon([(0, 0), (strip.width, 0)] + [(strip.width - i * strip.width / 30, strip.height - 6 + r.randrange(0, 8)) for i in range(31)], fill=(15, 15, 15, 255))
    fit_text(sd, sp["headline"], (24, 10, strip.width - 24, strip.height - 20), sp["highlight"], acc, maxl=2, serif=True, stroke=0)
    strip = strip.rotate(-4, expand=True, resample=Image.BICUBIC)
    im.paste(strip, (int(W * .03), int(H * .05)), strip)
    st = Image.new("RGBA", (int(W * .26), int(H * .15)), (0, 0, 0, 0))
    sd = ImageDraw.Draw(st)
    sd.rounded_rectangle((0, 0, st.width - 1, st.height - 1), radius=14, outline=(200, 30, 30, 255), width=8)
    sd.text((st.width * .12, st.height * .12), sp["badge"], font=S.font(st.height * .62), fill=(200, 30, 30, 255))
    st = st.rotate(12, expand=True, resample=Image.BICUBIC)
    im.paste(st, (int(W * .66), int(H * .50)), st)
    h = int(H * .50)
    put(im, face("CBS", h, emo_for(sp, "CBS")), int(W * .16), H, h, outline=None)
    put(im, face("PBS", h, emo_for(sp, "PBS")), int(W * .84), H, h, outline=None)
    put(im, face("NBC", int(H * .40), "calm"), int(W * .5), H, int(H * .40), outline=None)


LAY = {"versus": lay_versus, "center": lay_center, "shock": lay_shock, "quad": lay_quad, "paper": lay_paper}


def thumbnail(title, out, W=1280, H=720, layout=None):
    seed = zlib.crc32(title.encode())
    r = random.Random(seed)
    sp = thumb_spec(title, r, seed)
    if layout:
        sp["layout"] = layout
    acc = hexrgb(str(sp.get("accent", ""))) or r.choice(PAL)
    if max(acc) < 120:
        acc = r.choice(PAL)
    im = tbg(W, H, acc, r)
    LAY[sp["layout"]](im, ImageDraw.Draw(im), W, H, sp, acc, r)
    im.save(out, quality=90)
    return out


# ======================= INSTALL =======================
def install():
    S._init_prev = S.init
    S.init, S.draw_frame, S.build_extras, S.thumbnail = init2, draw_frame, build_extras, thumbnail
    o = S.to_scenes

    def ts(*a, **kw):
        sc = o(*a, **kw)
        CAP[:] = sc
        return sc
    S.to_scenes = ts
    orig = S.produce

    def produce(lines, sources, topic, W, H, fps, out, max_sec=None, tmp="work"):
        res = orig(lines, sources, topic, W, H, 12 if W >= H else fps, out, max_sec, tmp)
        mixed, tmpv = f"{tmp}/mixed.wav", out + ".tmp.mp4"
        mix(f"{tmp}/master.wav", mixed, [s for s in CAP if "t0" in s])
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", out, "-i", mixed, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", tmpv], check=True)
        os.replace(tmpv, out)
        return res
    S.produce = produce
