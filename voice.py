import subprocess, sys, wave
from config import PIPER_VOICE, WHISPER_MODEL
_w = None

def tts(text, out):
    subprocess.run([sys.executable, "-m", "piper", "-m", PIPER_VOICE, "-f", str(out)], input=text.encode(), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def duration(wav):
    with wave.open(str(wav)) as w: return w.getnframes() / w.getframerate()

def words(wav):
    global _w
    if _w is None:
        from faster_whisper import WhisperModel
        _w = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    segs, _ = _w.transcribe(str(wav), word_timestamps=True)
    return [(x.word.strip(), x.start, x.end) for s in segs for x in (s.words or [])]

def concat(wavs, gap, out):
    with wave.open(str(wavs[0])) as f: params = f.getparams()
    sil = b"\x00" * int(params.framerate * gap) * params.sampwidth * params.nchannels
    with wave.open(str(out), "wb") as o:
        o.setparams(params)
        for p in wavs:
            with wave.open(str(p)) as f: o.writeframes(f.readframes(f.getnframes()))
            o.writeframes(sil)
