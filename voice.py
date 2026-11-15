"""Neural TTS (edge-tts) per scene chunk with word-level timestamps for kinetic captions."""
import asyncio, subprocess
from pathlib import Path
import edge_tts
import config


def probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


async def _synth(text, mp3):
    for attempt in range(5):
        try:
            try:
                comm = edge_tts.Communicate(text, config.VOICE, rate=config.RATE, pitch=config.PITCH, boundary="WordBoundary")
            except TypeError:
                comm = edge_tts.Communicate(text, config.VOICE, rate=config.RATE, pitch=config.PITCH)
            marks = []
            with open(mp3, "wb") as f:
                async for ch in comm.stream():
                    if ch["type"] == "audio":
                        f.write(ch["data"])
                    elif ch["type"] == "WordBoundary":
                        marks.append(ch["offset"] / 1e7)
            if mp3.stat().st_size > 800:
                return marks
        except Exception as e:
            print("[tts] retry", attempt + 1, e)
            await asyncio.sleep(3 * (attempt + 1))
    raise RuntimeError("TTS failed: " + text[:60])


def align(words, marks, dur):
    if len(marks) == len(words):
        return marks
    total = sum(len(w) + 1 for w in words)
    t, out = 0.0, []
    for w in words:
        out.append(t)
        t += dur * (len(w) + 1) / total
    return out


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


async def _one(sc, wd, sem):
    async with sem:
        wav = wd / f"a_{sc['id']:04d}.wav"
        if sc["kind"] == "chapter":
            _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(sc["pause"]), str(wav)])
            sc.update(audio=str(wav), dur=sc["pause"], words=[])
            return
        mp3 = wd / f"a_{sc['id']:04d}.mp3"
        text = sc["narration"].replace("\u2014", ", ").replace("\u2013", "-")
        if not wav.exists():
            marks = await _synth(text, mp3)
            await asyncio.to_thread(_run, ["ffmpeg", "-y", "-i", str(mp3), "-ar", "44100", "-ac", "1",
                                           "-af", f"apad=pad_dur={sc['pause']}", str(wav)])
            sc["_marks"] = marks
        else:
            sc["_marks"] = []
        dur = probe(wav)
        words = sc["narration"].split()
        marks = align(words, sc.pop("_marks"), dur - sc["pause"])
        sc.update(audio=str(wav), dur=dur, words=[dict(w=w, t=t) for w, t in zip(words, marks)])


def synthesize(scenes, wd: Path, workers=4):
    wd.mkdir(parents=True, exist_ok=True)

    async def go():
        sem = asyncio.Semaphore(workers)
        await asyncio.gather(*[_one(s, wd, sem) for s in scenes])
    asyncio.run(go())
    t = 0.0
    for s in scenes:
        s["start"] = t
        t += s["dur"]
    return t
