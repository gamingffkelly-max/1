import json, re, hashlib, feedparser, trafilatura
from config import FEEDS, STATE

def load():
    return json.loads(STATE.read_text()) if STATE.exists() else {"used": [], "runs": []}
def save(s): STATE.write_text(json.dumps(s, indent=1))
def _c(h): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h or "")).strip()

def pick_topic():
    used, items = set(load()["used"]), []
    for url in FEEDS:
        try: d = feedparser.parse(url)
        except Exception: continue
        for e in d.entries[:20]:
            l = e.get("link", "")
            items.append({"id": hashlib.md5(l.encode()).hexdigest(), "title": _c(e.get("title")),
                          "summary": _c(e.get("summary")), "link": l,
                          "ts": tuple(e.get("published_parsed") or (0,) * 9)})
    fresh = [i for i in items if i["id"] not in used and len(i["title"]) > 15]
    if not fresh: raise RuntimeError("No fresh RSS items")
    fresh.sort(key=lambda i: i["ts"], reverse=True)
    main = fresh[0]
    text = ""
    try: text = trafilatura.extract(trafilatura.fetch_url(main["link"])) or ""
    except Exception: pass
    return {"main": main, "article": (text or main["summary"])[:6000], "related": fresh[1:7]}

def mark_used(topic, record):
    s = load(); s["used"] = (s["used"] + [topic["main"]["id"]])[-500:]
    s["runs"] = (s["runs"] + [record])[-50:]; save(s)
