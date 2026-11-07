import os
from pathlib import Path
ROOT = Path(__file__).parent
OUT = ROOT / "output"; OUT.mkdir(exist_ok=True)
STATE = ROOT / "state.json"
FEEDS = [l.strip() for l in (ROOT / "feeds.txt").read_text().splitlines() if l.strip() and not l.startswith("#")]
g = lambda k, d="": (os.getenv(k) or d).strip()
OLLAMA_URL, OLLAMA_MODEL = g("OLLAMA_URL", "http://127.0.0.1:11434"), g("OLLAMA_MODEL", "qwen2.5:7b")
PIPER_VOICE = g("PIPER_VOICE", str(ROOT / "voice" / "en_US-ryan-high.onnx"))
WHISPER_MODEL = g("WHISPER_MODEL", "small.en")
SD_MODEL = g("SD_MODEL", "SimianLuo/LCM_Dreamshaper_v7")
YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN = g("YT_CLIENT_ID"), g("YT_CLIENT_SECRET"), g("YT_REFRESH_TOKEN")
YT_CATEGORY = g("YT_CATEGORY", "27")
LONG_MIN = 105               # minutes (minimum target)
WRITE_BUDGET = 170 * 60      # seconds allowed for script+voice phase (keeps run under GitHub's 6h limit)
GAP, FPS = 0.6, 24
SHOT_LONG, SHOT_SHORT = 18, 4.5   # seconds per visual shot
STYLE_LONG = "stylized 3D animated film background, vibrant colors, soft cinematic lighting, highly detailed, empty scene, no people, no text"
STYLE_SHORT = "stylized 3D animated film background, vibrant colors, soft cinematic lighting, vertical composition, empty scene, no people, no text"
