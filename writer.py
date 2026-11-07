import json, requests
from config import *

RULES = ("Use only facts from the briefing or well-established public knowledge. Never invent statistics, quotes or sources. "
         "Mark estimates as estimates. No investment advice. Plain spoken English narration only: no markdown, headings, emojis or stage directions.")
SYS = "You are an award-winning documentary writer specialising in finance and economics. English only."

def ask(prompt, js=False, temp=0.8):
    body = {"model": OLLAMA_MODEL, "stream": False, "keep_alive": "1m", "options": {"temperature": temp, "num_ctx": 8192},
            "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": prompt}]}
    if js: body["format"] = "json"
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=3600); r.raise_for_status()
    return r.json()["message"]["content"].strip()

def jask(p):
    for _ in range(5):
        try: return json.loads(ask(p, js=True))
        except Exception: pass
    raise RuntimeError("LLM JSON failed")

def ctx(t):
    return (f"HEADLINE: {t['main']['title']}\nSUMMARY: {t['main']['summary']}\nARTICLE: {t['article']}\n"
            f"RELATED: {' | '.join(r['title'] for r in t['related'])}")

def plan_long(t):
    return jask(f"{ctx(t)}\n\nDesign a 1h50m cinematic finance documentary built on this story, told like a movie with a hook, rising tension, "
                f"characters, turning points and a resolution. {RULES}\nReturn JSON: {{\"title\":str,\"thumb_text\":\"max 3 words\","
                f"\"thumb_prompt\":\"dramatic visual\",\"logline\":str,\"chapters\":[{{\"heading\":str,\"beats\":str}}]}} with exactly 14 chapters; "
                f"the last chapter is the closing.")

def chapter(plan, t, i, heading, beats, tail):
    p = (f"{ctx(t)}\n\nDocumentary: {plan['title']} - {plan['logline']}\nWrite the narration of chapter {i+1}: '{heading}'. Beats: {beats}\n"
         f"Previous narration ended: ...{tail}\nStyle: cinematic, story-driven, vivid scenes, deep analysis, ~1200 words. {RULES}")
    txt = ask(p)
    for _ in range(3):
        if len(txt.split()) >= 1000: break
        txt += "\n" + ask(f"Continue this narration seamlessly for ~500 more words, same voice. {RULES}\n\n{txt[-1500:]}")
    return txt

def extra_chapter(plan, t, chapters):
    return jask(f"Documentary '{plan['title']}'. Existing chapters: {[c['heading'] for c in chapters]}. Propose ONE more deep-dive chapter "
                f"(new angle: history, counter-arguments, global impact, what-if) as JSON {{\"heading\":str,\"beats\":str}}.")

def short(t):
    return jask(f"{ctx(t)}\n\nWrite a ~65 second YouTube Short as a vivid mini-story with two named characters, strong first-line hook, "
                f"a twist, and a closing question. 170-190 words. {RULES}\nJSON: {{\"title\":str,\"thumb_text\":str,\"narration\":str}}")

def visuals(text, n, is_short):
    style = "3D stylized scenes with round-headed cartoon characters" if is_short else "photoreal cinematic scenes"
    d = jask(f"Narration:\n{text}\n\nWrite exactly {n} image prompts (one per ~{4 if is_short else 25}s) that illustrate this narration in order. "
             f"Style: {style}. Each under 40 words. No text, logos or real people. JSON: {{\"visuals\":[str]}}")
    v = [x for x in d.get("visuals", []) if isinstance(x, str)] or ["abstract financial city skyline at dusk"]
    return [v[k % len(v)] for k in range(n)]

def seo(t, plan, is_short):
    kind = "YouTube Short" if is_short else "long documentary"
    return jask(f"Topic: {t['main']['title']}\nVideo ({kind}): {plan.get('title')}\nWrite SEO metadata in English. Honest, no clickbait lies. "
                f"JSON: {{\"title\":\"max 85 chars, keyword first\",\"description\":\"3 short paragraphs with keywords\",\"tags\":[15 strings]}}")
