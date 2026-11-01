import os, math, zlib
from PIL import Image, ImageDraw
import studio as S

SS = 2
LW, LH, OX = 560, 540, 80
NAVY, NAVY_D, NAVY_L, TEE = (38, 52, 92), (18, 26, 52), (52, 68, 116), (68, 70, 76)
LIP_D = (88, 44, 28)
SKIN = {"CBS": ((48, 158, 74), (12, 66, 30), (130, 220, 150), (172, 90, 54)),
        "PBS": ((176, 42, 48), (78, 12, 18), (235, 125, 125), (150, 70, 46)),
        "NBC": ((234, 186, 38), (118, 82, 8), (255, 240, 150), (214, 160, 36)),
        "ABC": ((240, 240, 244), (88, 90, 102), (255, 255, 255), (168, 92, 56))}
U, F = 118, 112
SH = {-1: (86, 292), 1: (314, 292)}
REST = (10, 10, 10, 10, 0)


def P(pts, k):
    return [((x + OX) * k, y * k) for x, y in pts]


def poly(d, pts, k, fill, line=None, w=3):
    q = P(pts, k)
    d.polygon(q, fill=fill)
    if line:
        d.line(q + [q[0]], fill=line, width=max(1, int(w * k)), joint="curve")


def ell(d, k, b, fill, line=None, w=3):
    d.ellipse(((b[0] + OX) * k, b[1] * k, (b[2] + OX) * k, b[3] * k), fill=fill,
              outline=line, width=max(1, int(w * k)) if line else 0)


def draw_torso(d, k, nm):
    sk, ol, hi, lip = SKIN[nm]
    d.rectangle(((168 + OX) * k, 215 * k, (232 + OX) * k, 275 * k), fill=sk)
    poly(d, [(62, 300), (118, 262), (282, 262), (338, 300), (352, 540), (48, 540)], k, NAVY, NAVY_D, 3)
    poly(d, [(150, 262), (250, 262), (268, 540), (132, 540)], k, TEE, NAVY_D, 2)
    poly(d, [(165, 262), (235, 262), (200, 314)], k, sk, ol, 2)
    poly(d, [(112, 266), (152, 262), (190, 410), (150, 400), (124, 330)], k, NAVY_L, NAVY_D, 3)
    poly(d, [(288, 266), (248, 262), (210, 410), (250, 400), (276, 330)], k, NAVY_L, NAVY_D, 3)
    for i in range(13):
        t = i / 12
        x, y = 160 + 80 * t, 266 + 40 * math.sin(math.pi * t)
        c = [(120, 80, 50), (235, 225, 200), (30, 30, 30)][i % 3]
        ell(d, k, (x - 5, y - 5, x + 5, y + 5), c)
    d.rounded_rectangle(((226 + OX) * k, 340 * k, (284 + OX) * k, 362 * k), radius=6 * k, fill=(220, 30, 40))
    d.text(((230 + OX) * k, 345 * k), "YouTube", font=S.font(11 * k), fill=(255, 255, 255))
    for i, hh in enumerate((10, 16, 24)):
        d.rectangle(((184 + OX + i * 10) * k, (392 - hh) * k, (190 + OX + i * 10) * k, 392 * k), fill=(125, 135, 155))


def draw_arm(d, k, nm, s, th, ps, shy=0):
    sk, ol, hi, lip = SKIN[nm]
    sx, sy = SH[s]
    sy += shy
    t, p = math.radians(th), math.radians(ps)
    e = (sx + s * math.sin(t) * U, sy + math.cos(t) * U)
    w = (e[0] + s * math.sin(p) * F, e[1] + math.cos(p) * F)

    def seg(a, b, wd, col):
        d.line([((a[0] + OX) * k, a[1] * k), ((b[0] + OX) * k, b[1] * k)], fill=col, width=int(wd * k))
        r = wd / 2
        for q in (a, b):
            d.ellipse(((q[0] + OX - r) * k, (q[1] - r) * k, (q[0] + OX + r) * k, (q[1] + r) * k), fill=col)

    seg((sx, sy), e, 70, NAVY_D)
    seg(e, w, 60, NAVY_D)
    seg((sx, sy), e, 63, NAVY)
    seg(e, w, 53, NAVY)
    dx, dy = s * math.sin(p), math.cos(p)
    hx, hy = w[0] + dx * 20, w[1] + dy * 20
    ell(d, k, (hx - 27, hy - 27, hx + 27, hy + 27), sk, ol, 3)
    ell(d, k, (hx - s * 25 - 9, hy - 6 - 9, hx - s * 25 + 9, hy - 6 + 9), sk, ol, 2)
    for a in (-0.35, 0, 0.35):
        ca, sa = math.cos(a), math.sin(a)
        vx, vy = dx * ca - dy * sa, dx * sa + dy * ca
        d.line([((hx + OX + vx * 8) * k, (hy + vy * 8) * k), ((hx + OX + vx * 27) * k, (hy + vy * 27) * k)],
               fill=ol, width=max(1, int(2 * k)))


def draw_head(d, k, nm, e, bl, look, T, speaking):
    sk, ol, hi, lip = SKIN[nm]
    lid = tuple(int(c * .86) for c in sk)
    shapes = [(95, 95, 305, 240), (88, 52, 206, 150), (194, 52, 312, 150)]
    for b in shapes:
        ell(d, k, (b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3), ol)
    for b in shapes:
        ell(d, k, b, sk)
    ell(d, k, (112, 62, 150, 76), hi)
    c = 0.36 + 0.64 * bl - (0.08 * (1 - bl) if speaking else 0)
    for ex in (148, 252):
        ey, rx, ry = 108, 38, 30
        ell(d, k, (ex - rx, ey - ry, ex + rx, ey + ry), (250, 250, 250))
        px, py = ex + look, ey + 4
        ell(d, k, (px - 14, py - 14, px + 14, py + 14), (30, 26, 26))
        ell(d, k, (px - 7, py - 10, px, py - 3), (255, 255, 255))
        yl = ey - ry + 2 * ry * c
        pts = [(ex + rx * math.cos(math.radians(i)), min(ey + ry * math.sin(math.radians(i)), yl)) for i in range(0, 360, 6)]
        poly(d, pts, k, lid)
        if abs(yl - ey) < ry:
            xr = rx * math.sqrt(1 - ((yl - ey) / ry) ** 2)
            d.line([((ex - xr + OX) * k, yl * k), ((ex + xr + OX) * k, yl * k)], fill=ol, width=max(1, int(3 * k)))
        d.ellipse(((ex - rx + OX) * k, (ey - ry) * k, (ex + rx + OX) * k, (ey + ry) * k), outline=ol, width=max(1, int(3 * k)))
    for nx in (188, 212):
        ell(d, k, (nx - 3, 160, nx + 3, 166), ol)
    ho = e * 30 * (0.85 + 0.15 * math.sin(T * 23)) if speaking else 0
    wm = 1 - 0.14 * e

    def mx(x):
        return 200 + (x - 200) * wm
    if ho > 2:
        ell(d, k, (mx(122), 186, mx(278), 192 + ho), (52, 12, 18))
    ell(d, k, (mx(112), 186 + ho, mx(288), 222 + ho), lip, LIP_D, 3)
    ell(d, k, (mx(104), 166, mx(296), 198), lip, LIP_D, 3)
    ell(d, k, (mx(150), 172, mx(250), 180), tuple(min(255, v + 40) for v in lip))


def lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def _g(T, g, e):
    a = 0.5 + e
    if g == 0:
        return (20, 198 + 14 * math.sin(3.2 * T) * a, 20, 198 + 14 * math.sin(3.2 * T + 1.4) * a, 0)
    if g == 1:
        return (10, 10, 24, 190 + 8 * math.sin(5 * T), 0)
    if g == 2:
        return (12, 12, 16, 170 + 26 * max(0, math.sin(4.5 * T)) * a, 0)
    if g == 3:
        return (24, 175 + 8 * math.sin(2.5 * T), 24, 175 + 8 * math.sin(2.5 * T + 1), 0)
    if g == 4:
        return (12, 12, 16, 200 + 10 * math.sin(6 * T) * a, 0)
    return (30, 160, 30, 160, -8)


def pose(T, who, e):
    b = int(T / 3.2)
    u = T / 3.2 - b
    p = _g(T, zlib.crc32(f"{who}{b}".encode()) % 6, e)
    if u > 0.85:
        p = lerp(p, _g(T, zlib.crc32(f"{who}{b+1}".encode()) % 6, e), (u - 0.85) / 0.15)
    return p


def blink(T, ph):
    u = (T + ph * 1.3) % 3.6
    return 1.0 if u < 0.09 else (0.5 if u < 0.16 else 0.0)


class Rig:
    def __init__(self, nm, h):
        self.nm, self.sc = nm, h / LH
        self.Wf, self.Hf, self.k = int(LW * self.sc), int(h), self.sc * SS
        self.bare, self.rest = self._torso(False), self._torso(True)

    def _new(self, hh=LH):
        return Image.new("RGBA", (self.Wf * SS, int(hh * self.sc) * SS), (0, 0, 0, 0))

    def _torso(self, arms):
        im = self._new()
        d = ImageDraw.Draw(im)
        draw_torso(d, self.k, self.nm)
        if arms:
            for s in (-1, 1):
                draw_arm(d, self.k, self.nm, s, 10, 10)
        return im.reduce(SS)

    def frame(self, T, speaking, e, who, look, ph, ease=1.0):
        k = self.k
        if speaking:
            body = self.bare.copy()
            lay = self._new()
            d = ImageDraw.Draw(lay)
            p = lerp(REST, pose(T, who, e), ease)
            draw_arm(d, k, self.nm, -1, p[0], p[1], p[4])
            draw_arm(d, k, self.nm, 1, p[2], p[3], p[4])
            body.alpha_composite(lay.reduce(SS))
        else:
            body = self.rest.copy()
        hl = self._new(300)
        draw_head(ImageDraw.Draw(hl), k, self.nm, e if speaking else 0, blink(T, ph), look, T, speaking)
        hd = hl.reduce(SS)
        ang = 2.5 * math.sin(T * 4.4 + ph) * (0.5 + e) if speaking else math.sin(T * 1.7 + ph)
        hd = hd.rotate(ang, center=((OX + 200) * self.sc, 250 * self.sc), resample=Image.BICUBIC)
        dy = int((5 * e + 2 * math.sin(T * 3 + ph)) * self.sc) if speaking else int(4 * max(0, math.sin(T * 1.1 + ph)) ** 6 * self.sc)
        body.paste(hd, (0, dy), hd)
        return body


def portrait(nm, h):
    return Rig(nm, h).frame(1.0, False, 0, nm, 0, 0.0)


def save_jpgs():
    os.makedirs("out", exist_ok=True)
    for nm in S.ORDER:
        r = portrait(nm, 900)
        bg = Image.new("RGB", r.size, (255, 255, 255))
        bg.paste(r, (0, 0), r)
        bg.save(f"out/friday_characters_{nm.lower()}.jpg", quality=92)


def init(cfg):
    S._orig_init(cfg)
    S.SPR = {n: Rig(n, int(S.SEAT[n][2] * 1.15)) for n in S.ORDER}


def install():
    save_jpgs()
    S._orig_init = S.init
    S.init = init
    orig = S.to_scenes

    def ts(*a, **kw):
        sc = orig(*a, **kw)
        for i, s in enumerate(sc):
            s["prev"] = sc[i - 1]["who"] if i else None
        return sc
    S.to_scenes = ts
