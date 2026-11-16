"""Makes the pictures match the narration.
1. The local AI reads every narration chunk and writes what a camera could literally film for it (or NONE).
2. Candidate photos are collected (Pixabay / Pexels when keys exist, otherwise Wikimedia Commons public-domain photos).
3. A CLIP model scores every candidate against that description and the best one is used - but only if it is a real
   match. When nothing matches, the scene becomes clean kinetic typography instead of a wrong picture."""
import re, threading
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import config, script_writer

ORIG_DIRECT = script_writer.direct      # the rule-based layout skeleton (captured before main.py replaces it)
_clip = {"model": None, "proc": None, "failed": False}
_lock = threading.Lock()
STOP = set("the a an and of to in on at for with as is are was were it its this that these those from by into over "
           "photo picture image close up view shot".split())


def _tokens(t):
    return {w for w in re.findall(r"[a-z]{3,}", (t or "").lower()) if w not in STOP}


# ------------------------------------------------------------------ 1. what should the picture show?
def clean_visual(v):
    v = re.sub(r"^[\"'`*\s]+|[\"'`*.\s]+$", "", v or "")
    v = re.sub(r"^(a|an|the)\s+(photo|picture|image|shot)\s+of\s+", "", v, flags=re.I)
    if not v or v.upper().startswith("NONE") or not (2 <= len(v.split()) <= 10):
        return ""
    return v.lower()


def plan_visuals(chunks, mode="long", log=print):
    """-> list with one entry per chunk: a concrete visual phrase, '' (abstract: use typography) or None (not planned)."""
    out = [None] * len(chunks)
    try:
        import local_ai
        local_ai.start_budget(config.AI_VISUAL_MIN)
        for b in range(0, len(chunks), 8):
            if local_ai.time_left() < 60:
                log("[visuals] AI picture-planning time used up - the rest uses the keyword method")
                break
            part = chunks[b:b + 8]
            listing = "\n".join(f"{i + 1}: {c['text'][:240]}" for i, c in enumerate(part))
            ans = local_ai.chat(
                "For each numbered narration excerpt, write what a camera could literally photograph to illustrate it: one concrete "
                "scene with a subject and a setting, 3 to 8 words, for example 'poker chips on a green table' or 'woman writing in "
                "a journal at a desk'. The picture must show what is being talked about. If the excerpt is abstract and has no "
                "concrete visual, write NONE. Output exactly one line per excerpt in the form `number: scene`.\n\n" + listing,
                system="You are a photo editor choosing literal, accurate stock photos.", max_tokens=170, temperature=0.2)
            for ln in ans.splitlines():
                m = re.match(r"\s*(\d+)\s*[:.)-]\s*(.+)", ln)
                if m and 1 <= int(m.group(1)) <= len(part):
                    out[b + int(m.group(1)) - 1] = clean_visual(m.group(2))
            if (b // 8) % 10 == 0:
                log(f"[visuals] planned {min(b + 8, len(chunks))}/{len(chunks)} scenes")
    except Exception as e:
        log("[visuals] local AI unavailable for picture planning:", str(e)[:100])
    return out


def keyword_visual(text):
    ws = script_writer._kw(text)
    return next((v for w in ws for k, v in script_writer.VIS.items() if w.startswith(k)), "")


def direct(chunks, d, mode="long"):
    """Replacement for script_writer.direct: layout skeleton from the rules, pictures only where the narration is concrete."""
    base = ORIG_DIRECT(chunks, d, mode)
    plan = plan_visuals(chunks, mode)
    k = 0
    for i, (c, x) in enumerate(zip(chunks, base)):
        v = plan[i] if plan[i] is not None else keyword_visual(c["text"])
        x["caption"] = v
        if x["layout"] in ("stat", "quote"):          # text-driven moments keep their typographic layout
            x["media"] = "none"
        elif v:
            k += 1
            x.update(layout="hero" if k % 2 else "broll", media="photo", query=v, alt_query=" ".join(v.split()[:3]))
            if x["layout"] == "broll":
                x["theme"] = "ink"
        else:
            x.update(layout="serif" if i % 2 else "kinetic", media="none", query="", alt_query="")
    shown = sum(1 for x in base if x["media"] == "photo")
    print(f"[visuals] {shown}/{len(base)} scenes get a picture, the rest are typography", flush=True)
    return base


# ------------------------------------------------------------------ 2. candidate photos
def pixabay_candidates(m, query, portrait):
    if not config.PIXABAY_KEY:
        return []
    d = m._json("pixabay", "https://pixabay.com/api/", 0.7, params={
        "key": config.PIXABAY_KEY, "q": query[:100], "image_type": "photo", "per_page": 20, "safesearch": "true",
        "min_width": 1200, "orientation": "vertical" if portrait else "horizontal"})
    return [dict(uid=f"pb{h['id']}", prev=h.get("webformatURL") or h.get("previewURL"), full=h["largeImageURL"],
                 tags=h.get("tags", "")) for h in d.get("hits", [])]


def pexels_candidates(m, query, portrait):
    if not config.PEXELS_KEY or m.pexels_left <= 0:
        return []
    m.pexels_left -= 1
    d = m._json("pexels", "https://api.pexels.com/v1/search", 1.0, headers={"Authorization": config.PEXELS_KEY},
                params={"query": query, "per_page": 15, "orientation": "portrait" if portrait else "landscape"})
    return [dict(uid=f"px{p['id']}", prev=p["src"].get("medium") or p["src"]["small"],
                 full=p["src"].get("large2x") or p["src"]["large"], tags=p.get("alt", "")) for p in d.get("photos", [])]


def commons_candidates(m, query, portrait):
    """No key needed. Only public-domain / CC0 photos, so no credit line is ever required."""
    d = m._json("commons", "https://commons.wikimedia.org/w/api.php", 1.0, params={
        "action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6, "gsrlimit": 15,
        "prop": "imageinfo", "iiprop": "url|mime|extmetadata", "iiurlwidth": 1600, "format": "json"})
    out = []
    for p in d.get("query", {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        lic = str(ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")).lower()
        if ii.get("mime", "").startswith("image/") and ii.get("thumburl") and ("public domain" in lic or "cc0" in lic or "pd" == lic[:2]):
            out.append(dict(uid=f"wc{p['pageid']}", prev=ii["thumburl"], full=ii["thumburl"], tags=p.get("title", "")))
    return out


# ------------------------------------------------------------------ 3. CLIP scoring
_load_lock = threading.Lock()


def load_clip():
    """Loaded once. The lock matters: importing transformers from several threads at the same time fails randomly."""
    with _load_lock:
        if _clip["model"] is not None:
            return True
        if _clip["failed"]:
            return False
        try:
            from transformers import CLIPModel, CLIPProcessor
            _clip["model"] = CLIPModel.from_pretrained(config.CLIP_MODEL).eval()
            _clip["proc"] = CLIPProcessor.from_pretrained(config.CLIP_MODEL)
            print("[clip] picture-matching model loaded", flush=True)
            return True
        except Exception as e:
            _clip["failed"] = True
            print("[clip] not available, falling back to tag matching:", str(e)[:100], flush=True)
            return False


def clip_scores(caption, images):
    import torch
    with _lock, torch.no_grad():
        inp = _clip["proc"](text=[f"a photo of {caption}"], images=images, return_tensors="pt", padding=True)
        out = _clip["model"](**inp)
        return (out.image_embeds @ out.text_embeds.T).squeeze(-1).reshape(-1).tolist()


def tag_score(caption, tags):
    ct, tt = _tokens(caption), _tokens(tags)
    return len(ct & tt) / max(len(ct), 1)


def evaluate(m, caption, cands, use_clip):
    cands = [c for c in cands if c["prev"] and c["uid"] not in m.used][:14]
    if not cands:
        return None
    if use_clip:
        imgs, keep = [], []
        for c in cands:
            p = m._download(c["prev"], ".jpg")
            if p:
                try:
                    imgs.append(Image.open(p).convert("RGB"))
                    keep.append(c)
                except Exception:
                    pass
        if not imgs:
            return None
        scored = [(s + 0.03 * tag_score(caption, c["tags"]), c) for s, c in zip(clip_scores(caption, imgs), keep)]
    else:
        scored = [(tag_score(caption, c["tags"]), c) for c in cands]
    return max(scored, key=lambda t: t[0])


def best_match(ctx, caption, queries):
    m, use_clip = ctx.media, load_clip()
    threshold = config.CLIP_MIN if use_clip else config.TAG_MIN
    sources = [pixabay_candidates, pexels_candidates] if (config.PIXABAY_KEY or config.PEXELS_KEY) else [commons_candidates]
    best = None
    for q in queries:
        for fn in sources:
            res = evaluate(m, caption, fn(m, q, ctx.portrait), use_clip)
            if res and (best is None or res[0] > best[0]):
                best = res
            if best and best[0] >= threshold:
                break
        if best and best[0] >= threshold:
            break
    if not best or best[0] < threshold:
        return None
    score, c = best
    with m.lock:
        if c["uid"] in m.used:
            return None
        m.used.add(c["uid"])
    path = m._download(c["full"], ".jpg") or m._download(c["prev"], ".jpg")
    return (path, score) if path else None


# ------------------------------------------------------------------ 4. replaces editor.prepare_media
def prepare_media(scenes, ctx, log=print):
    todo = [s for s in scenes if s["layout"] in ("hero", "broll") and not s.get("asset")]
    stat = {"matched": 0, "typography": 0}
    if todo:
        load_clip()          # once, in the main thread, before the worker threads start

    def work(sc):
        caption = sc.get("caption") or sc.get("query") or ""
        queries = [q for q in (sc.get("query"), sc.get("alt_query")) if q]
        try:
            res = best_match(ctx, caption, queries) if caption else None
        except Exception as e:
            log(f"[visuals] scene {sc['id']}: {str(e)[:80]}")
            res = None
        if res:
            sc["asset"], sc["asset_kind"], sc["match"] = str(res[0]), "photo", round(res[1], 3)
            stat["matched"] += 1
        else:
            sc.update(layout="serif" if sc["id"] % 2 else "kinetic", media="none", theme="cream")
            stat["typography"] += 1

    with ThreadPoolExecutor(4) as ex:
        list(ex.map(work, todo))
    log(f"[visuals] pictures matched to the narration: {stat['matched']}, scenes that became typography because no photo "
        f"matched well enough: {stat['typography']}")
