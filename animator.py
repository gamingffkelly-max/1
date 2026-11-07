"""CPU character animation: rigged cartoon characters (walk, talk with audio lip-sync, gestures, blink),
camera-moving 3D-style backgrounds, drifting dust, vignette. Frames are piped straight into ffmpeg."""
import math, random, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageChops, ImageOps
from config import FPS

SS, BW, BH, OX = 2, 300, 410, 50
INK = (30, 30, 38, 255); SKIN = (252, 248, 240, 255)
COL = {"red": (214, 57, 57), "blue": (52, 120, 200), "green": (52, 150, 98), "yellow": (236, 190, 50), "orange": (230, 126, 34),
       "purple": (130, 80, 170), "teal": (40, 150, 160), "brown": (130, 85, 55), "grey": (120, 125, 135), "gray": (120, 125, 135),
       "black": (45, 45, 52), "white": (235, 235, 235), "pink": (224, 110, 160), "navy": (40, 60, 120), "maroon": (130, 40, 60)}

def _col(name, i=0):
    n = str(name or "").lower().strip()
    if n in COL: return COL[n]
    if n.startswith("#") and len(n) == 7:
        try: return tuple(int(n[k:k + 2], 16) for k in (1, 3, 5))
        except ValueError: pass
    return list(COL.values())[(i * 3 + 2) % len(COL)]

def _spec(c, i):
    jc = _col(c.get("jacket"), i); hat = c.get("hat", "none")
    return {"jacket": jc, "hat": hat if hat in ("cap", "bowler", "tophat", "none") else "none",
            "hatcol": (70, 100, 170) if hat == "cap" else (35, 35, 42), "shoe": (60, 45, 40, 255)}

def draw_char(sp, mode, t, mouth, flip):
    im = Image.new("RGBA", (BW * SS, BH * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    P = lambda *v: [(x + (OX if i % 2 == 0 else 0)) * SS for i, x in enumerate(v)]
    ph = t * 2 * math.pi * 1.2; walk = mode == "walk"
    oy = -abs(math.sin(ph)) * 7 if walk else math.sin(t * 2.2) * 2
    if mode == "react": oy -= abs(math.sin(t * 6)) * 22
    hy, sy, cy = 288 + oy, 200 + oy, 132 + oy
    jc = sp["jacket"] + (255,)
    for k, x0 in enumerate((90, 110)):                       # legs
        a = math.sin(ph + k * math.pi) * .55 if walk else (-.05 if k == 0 else .05)
        lift = max(0, math.sin(ph + k * math.pi)) * 12 if walk else 0
        fx, fy = x0 + 104 * math.sin(a), hy + 104 * math.cos(a) - lift
        d.line(P(x0, hy, fx, fy), fill=INK, width=7 * SS)
        d.ellipse(P(fx - 13, fy - 6, fx + 17, fy + 8), fill=sp["shoe"], outline=INK, width=3 * SS)
    if walk: aL, aR = math.sin(ph) * .5, -math.sin(ph) * .5   # arms
    elif mode == "talk": aL, aR = .12, .9 + .35 * math.sin(t * 5.5)
    elif mode == "point": aL, aR = .1, 1.5
    elif mode == "react": aL, aR = 2.5 + .2 * math.sin(t * 9), 2.5 + .2 * math.sin(t * 9 + 1)
    else: aL, aR = .1 + .04 * math.sin(t * 2), .1 + .04 * math.sin(t * 2 + 1)
    for sx, a, sg in ((64, aL, -1), (136, aR, 1)):
        hx, hyy = sx + sg * 80 * math.sin(a), sy + 80 * math.cos(a)
        d.line(P(sx, sy, hx, hyy), fill=INK, width=13 * SS); d.line(P(sx, sy, hx, hyy), fill=jc, width=8 * SS)
        d.ellipse(P(hx - 9, hyy - 9, hx + 9, hyy + 9), fill=SKIN, outline=INK, width=3 * SS)
    d.rounded_rectangle(P(62, 186 + oy, 138, 286 + oy), radius=20 * SS, fill=jc, outline=INK, width=4 * SS)   # torso
    d.polygon(P(88, 186 + oy, 112, 186 + oy, 100, 212 + oy), fill=(250, 250, 250, 255), outline=INK)
    for by in (232, 256): d.ellipse(P(97, by + oy, 103, by + 6 + oy), fill=INK)
    d.ellipse(P(48, cy - 52, 152, cy + 52), fill=SKIN, outline=INK, width=4 * SS)                             # head
    eh = 1 if (t % 3.1) < .12 else 6; lift = 6 if mode == "react" else (2 if mode in ("talk", "point") else 0)
    for ex in (82, 118):
        d.ellipse(P(ex - 5, cy - 2 - eh, ex + 5, cy - 2 + eh), fill=INK)
        d.line(P(ex - 11, cy - 17 - lift, ex + 11, cy - 17 - lift), fill=INK, width=4 * SS)
    if mode in ("talk", "point", "react"):
        m = .8 if mode == "react" else mouth; w, h = 9 + 7 * m, 2 + 13 * m
        d.ellipse(P(100 - w, cy + 26 - h, 100 + w, cy + 26 + h), fill=(70, 25, 35, 255), outline=INK, width=3 * SS)
    else:
        d.arc(P(84, cy + 12, 116, cy + 34), 20, 160, fill=INK, width=4 * SS)
    hc = sp["hatcol"] + (255,); hat = sp["hat"]
    if hat == "cap":
        d.chord(P(47, cy - 53, 153, cy + 53), 195, 345, fill=hc, outline=INK, width=4 * SS)
        d.rounded_rectangle(P(100, cy - 26, 168, cy - 13), radius=6 * SS, fill=hc, outline=INK, width=3 * SS)
    elif hat == "bowler":
        d.ellipse(P(66, cy - 74, 134, cy - 18), fill=hc, outline=INK, width=3 * SS); d.ellipse(P(52, cy - 32, 148, cy - 14), fill=hc, outline=INK, width=3 * SS)
    elif hat == "tophat":
        d.rectangle(P(74, cy - 100, 126, cy - 36), fill=hc, outline=INK, width=3 * SS); d.rectangle(P(74, cy - 52, 126, cy - 42), fill=(170, 40, 40, 255))
        d.ellipse(P(58, cy - 46, 142, cy - 26), fill=hc, outline=INK, width=3 * SS)
    else:
        for x in (88, 100, 112): d.line(P(x, cy - 52, x - 4 + (x - 100) // 4, cy - 68), fill=INK, width=4 * SS)
    return im.transpose(Image.FLIP_LEFT_RIGHT) if flip else im

def _vignette(W, H):
    y, x = np.mgrid[0:H, 0:W]; r = ((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2
    v = (255 * (1 - 0.32 * np.clip(r / 2, 0, 1) ** 0.9)).astype(np.uint8)
    return Image.merge("RGB", (Image.fromarray(v),) * 3)

def render_scene(a):
    """a: img,out,W,H,dur,cam,act,chars,env,seed,idx -> writes mp4 clip."""
    W, H = a["W"], a["H"]; n = max(1, round(a["dur"] * FPS)); cam, act, env = a["cam"], a["act"], a["env"]
    bg = ImageOps.fit(Image.open(a["img"]).convert("RGB"), (int(W * 1.3), int(H * 1.3)), Image.LANCZOS); B0, B1 = bg.size
    vig = _vignette(W, H); black = Image.new("RGB", (W, H)); rng = random.Random(a["seed"])
    motes = [(rng.random(), rng.random(), rng.uniform(1.5, 3.5), rng.uniform(.02, .07)) for _ in range(22)]
    chars = a["chars"][:2]; specs = [_spec(c, i) for i, c in enumerate(chars)]
    th = int(H * (0.42 if H > W else 0.56)); tw = int(th * BW / BH); gy = int(H * .93); bwid = int(th * 200 / BH)
    shadow = Image.new("RGBA", (int(bwid * .8), 22), (0, 0, 0, 0)); ImageDraw.Draw(shadow).ellipse((0, 0, shadow.width - 1, 21), fill=(0, 0, 0, 80))
    direction = 1 if a["idx"] % 2 == 0 else -1
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-threads", "1", a["out"]], stdin=subprocess.PIPE)
    for f in range(n):
        u = f / max(1, n - 1); t = f / FPS
        z = {"push_in": 1 + .18 * u, "pull_out": 1.18 - .18 * u}.get(cam, 1.15); bw, bh = B0 / z, B1 / z
        fx, fy = {"pan_left": (1 - u, .5), "pan_right": (u, .5), "tilt_up": (.5, 1 - u), "tilt_down": (.5, u), "drift": (u, u)}.get(cam, (.5, .5))
        x0, y0 = (B0 - bw) * fx, (B1 - bh) * fy
        fr = bg.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + bw, y0 + bh))
        dr = ImageDraw.Draw(fr)
        for mx, my, r, sp in motes:                                              # drifting dust
            px, py = (mx + t * sp * .5) % 1 * W, (my - t * sp * .3) % 1 * H
            dr.ellipse((px - r, py - r, px + r, py + r), fill=(255, 245, 220))
        if chars and act != "none":
            k = len(chars)
            for i in range(k):
                cx, flip = (.5, direction < 0) if k == 1 else ((.3, False) if i == 0 else (.7, True))
                if act == "walk": cx = (.25 + .5 * u if direction > 0 else .75 - .5 * u) if k == 1 else cx + (.08 * u if i == 0 else -.08 * u)
                mode = act
                if act in ("talk", "point") and k == 2 and (u < .5) != (i == 0): mode = "idle"
                mouth = env[f] if f < len(env) else 0
                ch = draw_char(specs[i], mode, t + i * .7, mouth, flip).resize((tw, th), Image.LANCZOS)
                px = int(cx * W - tw / 2); fr.paste(shadow, (int(cx * W - shadow.width / 2), gy - 12), shadow); fr.paste(ch, (px, int(gy - th * 400 / BH)), ch)
        fr = ImageChops.multiply(fr, vig); fd = min(1, f / 5, (n - 1 - f) / 5)
        if fd < 1: fr = Image.blend(black, fr, max(fd, 0))
        p.stdin.write(fr.tobytes())
    p.stdin.close()
    if p.wait() != 0: raise RuntimeError("ffmpeg failed for " + a["out"])
