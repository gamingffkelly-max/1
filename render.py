import subprocess, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps
from config import FPS, ROOT

def sh(cmd, cwd=None): subprocess.run(cmd, check=True, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def clip(img, dur, out, W, H, i):
    fr = max(1, round(dur * FPS)); bw, bh = int(W * 1.25) // 2 * 2, int(H * 1.25) // 2 * 2
    cy = "ih/2-(ih/zoom/2)"; cx = "iw/2-(iw/zoom/2)"
    z, x, y = [("min(zoom+0.0004,1.18)", cx, cy), ("if(eq(on,0),1.18,max(zoom-0.0004,1.0))", cx, cy),
               ("1.15", f"(iw-iw/zoom)*on/{fr}", cy), ("1.15", f"(iw-iw/zoom)*(1-on/{fr})", cy)][i % 4]
    vf = (f"scale={bw}:{bh}:force_original_aspect_ratio=increase:flags=lanczos,crop={bw}:{bh},"
          f"zoompan=z='{z}':x='{x}':y='{y}':d={fr}:s={W}x{H}:fps={FPS},vignette=PI/5,"
          f"fade=t=in:d=0.2,fade=t=out:st={max(dur - 0.2, 0):.2f}:d=0.2,format=yuv420p")
    sh(["ffmpeg", "-y", "-threads", "1", "-i", str(img), "-vf", vf, "-frames:v", str(fr), "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "24", "-threads", "1", str(out)])

def _t(s): return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"
def _s(w): return w.replace("{", "").replace("}", "").replace("\\", "")

def ass(path, W, H, short, words, titles):
    sz, mv, ol = (int(W * .095), int(H * .27), 5) if short else (int(H * .058), int(H * .06), 3)
    hdr = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\n\n[V4+ Styles]\n"
           "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
           f"Style: Cap,Liberation Sans,{sz},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{ol},2,2,30,30,{mv},1\n"
           f"Style: Title,Liberation Sans,{int(sz * 1.3)},&H0000D7FF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,2,0,1,{ol},3,5,40,40,0,1\n\n"
           "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    ev = []
    if short:
        for k, (w, a, b) in enumerate(words):
            e = words[k + 1][1] if k + 1 < len(words) else b
            ev.append(f"Dialogue: 0,{_t(a)},{_t(max(e, a + .08))},Cap,,0,0,0,,{_s(w)}")
    for t, h in titles:
        ev.append(f"Dialogue: 1,{_t(t + .3)},{_t(t + 4.5)},Title,,0,0,0,,{{\\fad(500,500)}}{_s(h)}")
    Path(path).write_text(hdr + "\n".join(ev) + "\n", encoding="utf-8")

def assemble(work, clips, wav, out):
    (work / "list.txt").write_text("".join(f"file '{c.name}'\n" for c in clips))
    music = list((ROOT / "assets" / "music").glob("*.mp3"))
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-i", str(wav)]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(random.choice(music))]
        fc = "[0:v]ass=captions.ass[v];[2:a]volume=0.07[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]"
    else:
        fc = "[0:v]ass=captions.ass[v];[1:a]anull[a]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)]
    sh(cmd, cwd=work)

def thumbnail(bg, text, out):
    im = ImageOps.fit(Image.open(bg).convert("RGB"), (1280, 720), method=Image.LANCZOS)
    im = ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(1.3)).enhance(1.3)
    d = ImageDraw.Draw(im, "RGBA")
    for x in range(1280): d.line([(x, 0), (x, 720)], fill=(0, 0, 0, int(210 * max(0, 1 - x / 900))))
    d.rectangle([0, 0, 24, 720], fill=(255, 40, 40, 255))
    fp = next((p for p in [ROOT / "assets" / "font.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                           "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"] if Path(p).exists()), None)
    words = text.upper().split()[:4]; size = 190
    while size > 60:
        f = ImageFont.truetype(str(fp), size) if fp else ImageFont.load_default()
        if max(d.textlength(w, font=f) for w in words) < 760 and size * 1.15 * len(words) < 640: break
        size -= 10
    y = (720 - size * 1.15 * len(words)) / 2
    for k, w in enumerate(words):
        col = (255, 212, 0) if k == len(words) - 1 else (255, 255, 255)
        d.text((70, y + k * size * 1.15), w, font=f, fill=col, stroke_width=10, stroke_fill=(0, 0, 0))
    im.save(out, quality=92)
