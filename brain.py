import os, re, json, time, html, hashlib
from urllib.parse import urlparse
import feedparser, requests

feedparser.USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
OLLAMA = "http://127.0.0.1:11434/api/generate"
MODEL = os.getenv("MODEL", "qwen2.5:3b")

FEEDS = [
 "https://feeds.bbci.co.uk/news/world/rss.xml",
 "https://www.aljazeera.com/xml/rss/all.xml",
 "https://www.theguardian.com/world/rss",
 "https://feeds.npr.org/1004/rss.xml",
 "https://rss.dw.com/rdf/rss-en-world",
 "https://www.france24.com/en/rss",
 "https://feeds.skynews.com/feeds/rss/world.xml",
 "http://rss.cnn.com/rss/edition_world.rss",
 "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
 "https://feeds.washingtonpost.com/rss/world",
 "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms",
 "https://www.japantimes.co.jp/feed/",
 "https://www.euronews.com/rss?format=mrss&level=theme&name=news",
 "https://www.channelnewsasia.com/rssfeeds/8395986",
 "https://www.thehindu.com/news/international/feeder/default.rss",
 "https://www.scmp.com/rss/91/feed",
 "https://www.independent.co.uk/news/world/rss",
 "https://www.straitstimes.com/news/world/rss.xml",
 "https://www.cbc.ca/webfeed/rss/rss-world",
]
NAMES = {"bbci.co.uk": "BBC News", "aljazeera.com": "Al Jazeera", "theguardian.com": "The Guardian",
 "npr.org": "NPR", "dw.com": "DW News", "france24.com": "France 24", "skynews.com": "Sky News",
 "cnn.com": "CNN", "nytimes.com": "The New York Times", "washingtonpost.com": "The Washington Post",
 "indiatimes.com": "The Times of India", "japantimes.co.jp": "The Japan Times", "euronews.com": "Euronews",
 "channelnewsasia.com": "CNA", "thehindu.com": "The Hindu", "scmp.com": "SCMP",
 "independent.co.uk": "The Independent", "straitstimes.com": "The Straits Times", "cbc.ca": "CBC News"}
SKIP = ["nfl", "nba", "mlb", "premier league", "football", "soccer", "cricket match", "tennis", "golf", "oscars",
        "grammy", "celebrity", "recipe", "horoscope", "box office", "fashion", "royal family", "podcast"]
STOP = set("this that with from have will what when your about after their they been more than into over says said just could would amid news live latest".split())

SYS = ("You are a world-class news analyst and scriptwriter. You write vivid, deeply analytical spoken dialogue in "
       "English. Be factual, balanced and respectful. Attribute claims ('supporters say', 'critics say'). Never invent "
       "quotes or precise statistics you are not sure about. Never celebrate violence or suffering.")


def llm(prompt, system=SYS, tokens=2200, temp=0.8):
    for _ in range(3):
        try:
            r = requests.post(OLLAMA, json={"model": MODEL, "prompt": prompt, "system": system, "stream": False,
                "options": {"temperature": temp, "num_predict": tokens, "num_ctx": 8192}}, timeout=3600)
            t = r.json().get("response", "").strip()
            if t:
                return t
            print("llm empty response:", str(r.text)[:200])
        except Exception as e:
            print("llm error:", e)
            time.sleep(5)
    return ""


def src_name(u, f):
    d = urlparse(u).netloc.replace("www.", "")
    for k, v in NAMES.items():
        if k in d:
            return v
    return (f.feed.get("title") or d).split(" - ")[0][:40]


def fetch_articles(days=2):
    out, cutoff = [], time.time() - days * 86400
    for u in FEEDS:
        try:
            f = feedparser.parse(u)
            for e in f.entries[:25]:
                title = html.unescape(e.get("title", "")).strip()
                summ = re.sub(r"<[^>]+>", " ", html.unescape(e.get("summary", "")))
                summ = re.sub(r"\s+", " ", summ).strip()[:500]
                ts = e.get("published_parsed") or e.get("updated_parsed")
                if ts and time.mktime(ts) < cutoff:
                    continue
                low = (title + " " + summ).lower()
                if not title or any(k in low for k in SKIP):
                    continue
                date = time.strftime("%B %d, %Y", ts) if ts else time.strftime("%B %d, %Y")
                out.append({"title": title, "summary": summ, "source": src_name(u, f), "date": date})
        except Exception as ex:
            print("feed failed", u, ex)
    print(len(out), "world news articles")
    return out


def toks(s):
    return {w for w in re.findall(r"[a-z]{4,}", s.lower()) if w not in STOP}


def pick_topic(arts, used, prefix):
    for a in arts:
        a["tok"] = toks(a["title"])
    scored = []
    for a in arts:
        rel = [b for b in arts if b is not a and b["source"] != a["source"] and len(a["tok"] & b["tok"]) >= 2]
        scored.append((len(set(b["source"] for b in rel)) * 3 + len(rel), a, rel))
    scored.sort(key=lambda x: -x[0])
    for _, a, rel in scored:
        h = prefix + hashlib.md5(a["title"].lower().encode()).hexdigest()[:10]
        if h in used:
            continue
        return h, a, [a] + rel[:7]
    raise RuntimeError("no fresh topic found")


def clean_topic(t):
    return re.split(r"\s[-|–—]\s", t)[0].strip()


def facts_text(group):
    return "\n".join(f"[S{i+1}] {a['title']} — {a['summary']}" for i, a in enumerate(group))


# tolerant: "1. ABC:", "**NBC**:", "CBS (benefits):", "PBS - text"
LINE = re.compile(r"^[\W\d_]*(CBS|PBS|NBC|ABC)\b(?:\s*\([^)]*\))?[\W_]*?[:：\-–—]\s*(.+)$", re.I)


def parse(text, allowed):
    out = []
    for raw in text.splitlines():
        m = LINE.match(raw.strip())
        if not m:
            continue
        who = m.group(1).upper()
        if who not in allowed:
            continue
        body = re.sub(r"\((?!S\d)[^)]{0,50}\)", "", m.group(2))
        body = re.sub(r"[*_#`]+", "", body)
        body = re.sub(r"\s+", " ", body).strip()
        if len(body.split()) >= 3:
            out.append({"who": who, "text": body})
    return out


FALLBACK_TITLES = ["What happened and the timeline", "Who is involved and what they want", "Background and history",
 "The case for: benefits and opportunities", "The case against: harms and risks", "Impact on ordinary people",
 "Impact on the global economy and trade", "Impact on politics and diplomacy", "How other countries are reacting",
 "What the media gets right and wrong", "Myths and misinformation", "Possible scenarios: best, base and worst case",
 "Lessons from similar events in history", "What international law and institutions say", "What to watch next",
 "Long-term vs short-term effects"]


def outline(topic, facts, n=16):
    t = llm(f"Topic: {topic}\nNews facts:\n{facts}\n\nGive {n} numbered section titles for a deep two-hour debate about this "
            f"news story. Do not include a conclusion section. Output only the numbered list.", tokens=500)
    titles = [re.sub(r"^\W*\d+[\).:-]?\s*", "", l).strip(" *#-") for l in t.splitlines() if re.match(r"^\W*\d+", l)]
    titles = [x for x in titles if 5 < len(x) < 110]
    i = 0
    while len(titles) < n:
        titles.append(FALLBACK_TITLES[i % len(FALLBACK_TITLES)])
        i += 1
    return titles[:n]


def section_prompt(topic, facts, title, k, covered, tail, words):
    return f"""Write one section of a long, deep world-news debate show.
TOPIC: {topic}
SECTION TITLE: {title}
NEWS FACTS (cite as [S1], [S2] ... right after the sentence that uses a fact):
{facts}

CHARACTERS:
NBC (golden, neutral moderator): opens with a sharp, deep question, challenges BOTH sides, never takes a side.
CBS (green): argues the benefits, positive angles, opportunities and what supporters say, with evidence.
PBS (red): argues the harms, risks, costs and what critics say, with evidence.

RULES:
- Output only dialogue lines. Each line starts with CBS:, PBS: or NBC: (uppercase, colon).
- CBS and PBS rebut each other directly and argue hard but respectfully. NBC keeps asking deeper follow-up questions.
- Use evidence: facts, history, mechanisms, analogies, examples and expert knowledge. Attribute claims to supporters or critics.
- Natural spoken English, 1-4 sentences per line, about {words} words in total. No stage directions, no markdown.
Already covered, do not repeat: {'; '.join(covered[-8:]) or 'nothing yet'}
Last lines so far:
{tail}
Begin:"""


def intro_lines(topic, facts):
    t = llm(f"Write the opening monologue of ABC, the white host who ONLY opens the show, introduces the topic and the "
            f"guests. 6 to 8 lines, each starting with 'ABC:'. State today's topic, why it matters right now, 4 specific "
            f"things viewers will learn, and what the debate will cover. Mention the three guests: NBC (golden, asks deep "
            f"questions), CBS (green, benefits) and PBS (red, harms).\nTopic: {topic}\nFacts:\n{facts}", tokens=800)
    ls = parse(t, {"ABC"})
    if len(ls) < 3:
        ls = [{"who": "ABC", "text": f"Welcome to the table. I'm ABC, the white one, and I open the show. Today's topic: {topic}."},
              {"who": "ABC", "text": "In the next two hours you will learn what happened, why it matters, who benefits, who gets hurt, and how to think about it."},
              {"who": "ABC", "text": "Today's guests are NBC, who asks the deep questions, CBS, who brings the benefits, and PBS, who brings the risks."}]
    if "abc" not in ls[0]["text"].lower():
        ls[0]["text"] = "Welcome to the table. I'm ABC, the white one, and my only job is to open the show. " + ls[0]["text"]
    ls += [
        {"who": "ABC", "text": "Now let me hand over so our guests can introduce themselves."},
        {"who": "NBC", "text": "I'm NBC, the golden one. I'm neutral. I ask deep questions to both sides and I keep this debate honest."},
        {"who": "CBS", "text": "I'm CBS, the green one. I bring the benefits, the opportunities and the positive side of every story."},
        {"who": "PBS", "text": "And I'm PBS, the red one. I bring the harms, the risks and the criticism nobody wants to hear."},
        {"who": "ABC", "text": "That's our table. NBC, it's all yours."},
        {"who": "NBC", "text": "Thank you, ABC. CBS, PBS, let's begin."},
    ]
    return ls


CLOSING = [
    {"who": "NBC", "text": "That's the full picture. CBS showed you the upside, PBS showed you the risks, and the smart move is to check the facts and decide for yourself."},
    {"who": "NBC", "text": "This show discusses news and viewpoints for information only. If it helped you, subscribe, and tell us in the comments which side you were on."},
]


def write_script(topic, group, target_min=112, max_sections=26):
    facts = facts_text(group)
    target = int(target_min * 155)
    titles = outline(topic, facts)
    lines = intro_lines(topic, facts)
    words = sum(len(l["text"].split()) for l in lines)
    covered, k, fails = [], 0, 0

    def section(title, w):
        tail = "\n".join(f"{l['who']}: {l['text']}" for l in lines[-3:])
        txt = llm(section_prompt(topic, facts, title, k, covered, tail, w), tokens=2400)
        got = parse(txt, {"CBS", "PBS", "NBC"})
        if not got:
            print("section parse failed, raw output:", txt[:300].replace("\n", " | "))
        return got

    while words < target and k < max_sections and fails < 4:
        title = titles[k] if k < len(titles) else f"Audience questions and sharper rebuttals, round {k - len(titles) + 1}"
        got = section(title, 1100)
        w = sum(len(l["text"].split()) for l in got)
        if w < 120:
            fails += 1
            continue
        fails = 0
        lines += got
        words += w
        covered.append(title)
        k += 1
        print(f"section {k}: +{w} words, total {words}/{target}", flush=True)
    got = section("Final verdict, key takeaways and what to watch next", 600)
    if sum(len(l["text"].split()) for l in got) >= 100:
        lines += got
    lines += CLOSING
    if len(lines) < 30:
        raise RuntimeError("script too short")
    return lines


def write_short(topic, group):
    facts = facts_text(group[:3])
    prompt = f"""Write a 50-second world-news debate for a YouTube Short. Topic: {topic}
Facts:
{facts}
Output exactly 8 lines, each starting with a name and colon, in this order:
ABC: (one sentence: today's topic)
NBC: (sharp question)
CBS: (benefit, 2 sentences)
PBS: (harm, 2 sentences)
CBS: (rebuttal, 1 sentence)
PBS: (rebuttal, 1 sentence)
NBC: (neutral verdict)
NBC: (asks viewers which side they are on)
Plain spoken English, under 22 words per line. Do not number the lines."""
    for _ in range(3):
        t = llm(prompt, tokens=600)
        ls = parse(t, {"ABC", "NBC", "CBS", "PBS"})
        if len(ls) >= 5:
            return ls[:9]
        print("short parse failed, raw output:", t[:300].replace("\n", " | "))
    a = group[0]
    first = re.split(r"(?<=[.!?])\s+", (a.get("summary") or a["title"]))[0][:170]
    print("using built-in short fallback script")
    return [
        {"who": "ABC", "text": f"Today's topic: {topic}."},
        {"who": "NBC", "text": "CBS, PBS, what does this mean for ordinary people?"},
        {"who": "CBS", "text": f"{first} [S1] The positive side is that it can create openings for dialogue and change."},
        {"who": "PBS", "text": "But the risks are real. Costs and consequences can fall hardest on ordinary people."},
        {"who": "CBS", "text": "Progress often starts with uncomfortable moments like this."},
        {"who": "PBS", "text": "Progress means little if the harm comes first."},
        {"who": "NBC", "text": "Both sides have a point. Check the facts and decide for yourself."},
        {"who": "NBC", "text": "Which side are you on? Tell us in the comments."},
    ]


def clean(t, names):
    t = re.sub(r"https?://\S+|www\.\S+", "", t)
    for n in names:
        t = re.sub(re.escape(n), "", t, flags=re.I)
    t = re.sub(r"[<>]", "", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def seo(topic, short=False):
    names = list(NAMES.values())
    title = llm(f"Write ONE click-worthy but honest YouTube title (max 80 characters, no quotes, no hashtags) for a world "
                f"news debate video about: {topic}. Output the title only.", tokens=40, temp=0.9)
    title = title.split("\n")[0].strip(' "\'*#')
    if not 15 < len(title) <= 90:
        title = f"{topic[:70]}: Benefits vs Risks"
    desc = llm(f"Write an SEO-optimised YouTube description of 180-260 words for a world news debate video about: {topic}. "
               f"Two hook sentences with keywords first, then what viewers will learn as short sentences. Characters: "
               f"CBS (benefits), PBS (risks), NBC (neutral questions), ABC (host). NO links, NO mention of where "
               f"information came from, NO news outlet names.", tokens=500)
    desc = clean(desc, names) or f"A deep debate on {topic}. CBS shows the benefits, PBS shows the risks, NBC asks the hard questions."
    desc += "\n\nThis video discusses news and viewpoints for information only.\n\n#worldnews #news #internationalnews #debate"
    if short:
        title = title[:80] + " #Shorts"
        desc += " #Shorts"
    tg = llm(f"Give 15 YouTube tags (comma separated, no hashtags, world news and international affairs) for: {topic}", tokens=150)
    tags, tot = [], 0
    for x in re.split(r"[,\n]", tg):
        x = re.sub(r"^\W*\d+[\).]?\s*", "", x).strip(' "#')
        if 2 < len(x) <= 30 and tot + len(x) < 450:
            tags.append(x)
            tot += len(x)
    tags = tags or ["world news", "international news", "news debate", "trending news"]
    return title, desc, tags


def friday_text(topic):
    t = llm(f"Write a short engaging community post (70-100 words) for a world news YouTube channel about: {topic}. "
            f"End with a question to the audience. Add 3 hashtags. No links, no source names.", tokens=250)
    return clean(t, list(NAMES.values())) or f"{topic}\n\nBenefits or risks? Tell us in the comments.\n\n#worldnews #news #debate"
