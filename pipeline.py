import time, logging
from concurrent.futures import ThreadPoolExecutor
import rss_feed, writer, voice, visuals, render, uploader
from config import *
log = logging.getLogger("pipe")

def narrate(work, idx, heading, text, short):
    wav = work / f"n{idx:02d}.wav"; voice.tts(text, wav); d = voice.duration(wav)
    return {"heading": heading, "wav": wav, "dur": d, "text": text, "words": voice.words(wav) if short else [],
            "vis": writer.visuals(text, max(1, round(d / (4.5 if short else 25))), short)}

def build(kind):
    t0 = time.time(); short = kind == "short"; W, H = (720, 1280) if short else (1280, 720)
    topic = rss_feed.pick_topic(); log.info(f"[{kind}] topic: {topic['main']['title']}")
    work = OUT / f"{time.strftime('%Y%m%d_%H%M')}_{kind}"; work.mkdir(parents=True); segs = []
    if short:
        plan = writer.short(topic); segs.append(narrate(work, 0, None, plan["narration"], True))
    else:
        plan = writer.plan_long(topic); chs = plan["chapters"]; body, closing = chs[:-1], chs[-1]
        st = {"total": 0.0, "tail": ""}; extras = 0
        def do(ch):
            log.info(f"chapter {len(segs) + 1}: {ch['heading']} ({(time.time() - t0) / 60:.0f} min elapsed)")
            s = narrate(work, len(segs), ch["heading"], writer.chapter(plan, topic, len(segs), ch["heading"], ch["beats"], st["tail"]), False)
            segs.append(s); st["total"] += s["dur"] + GAP; st["tail"] = s["text"][-300:]
        over = lambda: time.time() - t0 > WRITE_BUDGET
        for ch in body:
            if over(): log.warning("time budget reached, jumping to closing"); break
            do(ch)
        while st["total"] < LONG_MIN * 60 - 300 and extras < 4 and not over():
            ch = writer.extra_chapter(plan, topic, body + [closing]); body.append(ch); extras += 1; do(ch)
        do(closing)
    t, scenes, cw, titles = 0.0, [], [], []
    for s in segs:
        if s["heading"]: titles.append((t, s["heading"]))
        per = (s["dur"] + GAP) / len(s["vis"]); scenes += [(p, per) for p in s["vis"]]
        cw += [(w, t + a, t + b) for w, a, b in s["words"]]; t += s["dur"] + GAP
    log.info(f"narration {t / 60:.1f} min, {len(scenes)} scenes")
    jobs = []
    for i, (p, d) in enumerate(scenes):
        img = work / f"i{i:04d}.png"; visuals.image(p, img, short, i); jobs.append((img, d, work / f"c{i:04d}.mp4", W, H, i))
        if i % 20 == 0: log.info(f"image {i}/{len(scenes)}")
    log.info("rendering clips")
    with ThreadPoolExecutor(4) as ex: list(ex.map(lambda a: render.clip(*a), jobs))
    voice.concat([s["wav"] for s in segs], GAP, work / "all.wav")
    render.ass(work / "captions.ass", W, H, short, cw, titles)
    final = work / "final.mp4"; log.info("assembling final video")
    render.assemble(work, [j[2] for j in jobs], work / "all.wav", final)
    thumb = None
    if not short:
        visuals.image(plan.get("thumb_prompt", plan["title"]), work / "tb.png", False, 7, big=True); thumb = work / "thumb.jpg"
        render.thumbnail(work / "tb.png", plan.get("thumb_text", "THE TRUTH"), thumb)
    seo = writer.seo(topic, plan, short); d = seo["description"] + "\n\n"
    if not short and titles: d += "\n".join(f"{int(a // 60):02d}:{int(a % 60):02d} {h}" for a, h in titles) + "\n\n"
    d += f"Source: {topic['main']['link']}\nNot financial advice. Narration and visuals are AI-generated.\n" + ("#Shorts #Finance" if short else "#Finance #Economics")
    title = seo["title"] + (" #Shorts" if short and "#Shorts" not in seo["title"] else "")
    log.info("uploading"); vid = uploader.upload(final, title, d, seo.get("tags", []), thumb)
    rss_feed.mark_used(topic, {"kind": kind, "title": title, "video": vid, "time": time.strftime("%F %T")})
    log.info(f"PUBLISHED https://youtu.be/{vid}")
