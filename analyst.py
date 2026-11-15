"""Deep analysis + original script writing with the LOCAL AI, following a three-stage method:
STAGE 1  book intelligence: read the sources in chunks, build an IDEA LEDGER and a terminology list
STAGE 2  adaptation: chapter outline, then every chapter written with the seven-layer explanation method
STAGE 3  quality control: unsupported numbers/quotes removed, ledger coverage audit (missing points are added),
         similarity guard against copying."""
import math, random, re
import config, local_ai

SYS = ("You are an elite audiobook adaptation director and professional storyteller. You write natural, intelligent, deeply "
       "informative spoken English that preserves the substance of a book instead of skimming it.")
STYLE = ("Write ONLY clean spoken narration ready for text-to-speech: natural paragraphs, no headings, no bullet points, no "
         "tables, no stage directions, no chapter labels, no sound or music cues, no phrases like 'in this video'. Spell out "
         "abbreviations. One main idea per paragraph, paragraphs under 70 words, varied sentence length. Use ONLY the ledger "
         "for facts: never invent quotes, statistics, studies, names, dates or events, and keep the author's uncertainty (do "
         "not turn 'may' into 'does'). Put every idea in fresh words and never reuse phrasing from the notes.")
SEVEN = ("Explain every major idea with these layers whenever the ledger supports them: (1) the idea stated precisely, (2) the "
         "stakes: why it matters and which problem it answers, (3) the mechanism: how it works step by step in the author's "
         "reasoning, (4) the evidence: studies, observations, historical support, (5) the illustration: the author's own examples, "
         "stories or analogies, (6) the complication: limits, exceptions, objections, (7) the consequence and how it leads to the "
         "next idea. Skip a layer when the ledger does not support it; never invent one.")
AVOID = ("Avoid artificial suspense, excessive rhetorical questions, generic motivational speeches, empty dramatic statements, "
         "stock AI phrases such as 'delve', 'tapestry', 'game-changer' or 'in today's fast-paced world', and repeated explanations.")
GENRE_GUIDE = {
    "Psychology & Mind": "Narrate like a skilled psychology educator: explain the mechanism, who ran an experiment and how, what it found, how it was interpreted, and separate evidence from speculation.",
    "Business & Money": "Narrate like a clear business educator: preserve frameworks, business models, case studies, data, strategic reasoning and the risks.",
    "History & Politics": "Narrate like a premium historical documentary: set time and place, introduce the figures, explain circumstances, keep the sequence of decisions and consequences and the historical disputes.",
    "Science & Technology": "Narrate with scientific clarity: explain mechanisms and processes, preserve discoveries and experimental evidence, keep terminology accurate and state the limits.",
    "Philosophy & Wisdom": "Narrate with intellectual precision: keep complete chains of reasoning, premises, objections and responses, and explain abstract terms plainly.",
    "Biography & Memoir": "Narrate with human depth: keep the chronology, the personal experiences, important relationships and the author's reflections.",
    "Fiction & Literature": "Narrate as a literary storyteller: keep the order of events, the characters, the themes and the emotional turning points, and never reveal a twist early.",
}
DEFAULT_GUIDE = ("Narrate like a thoughtful mentor and teacher: explain the principles deeply, keep the author's reasoning and the "
                 "useful examples, explain methods and their limits, and avoid repetitive motivational language.")
KINDS = ("IDEA", "WHY", "HOW", "EVIDENCE", "EXAMPLE", "PERSON", "TERM", "LIMIT", "CONCLUSION")
STOP = set("the a an and or but if of to in on at for with as is are was were be been it this that these those you your they "
           "their we our he she his her not no so than then there here from by about into over just very more most can could "
           "will would should have has had do does did what which who how why when also book author".split())

GENERIC_CHAPTERS = [
    ("Why This Book Matters", "the problem the book tackles and why it still matters today"),
    ("The Core Idea", "the central thesis explained precisely"),
    ("How We Usually Get It Wrong", "the habits of thinking that the book challenges"),
    ("The Framework Behind It", "the structure or method the author proposes"),
    ("A Closer Look At The Evidence", "the reasoning, research and examples that support the argument"),
    ("Stories That Make It Real", "the author's examples and cases"),
    ("Putting It Into Practice", "the practical methods the book describes"),
    ("Obstacles Along The Way", "what makes the ideas hard to apply"),
    ("What Critics Say", "limits, objections and balanced criticism of the book"),
    ("Connecting The Dots", "how the individual ideas combine into one picture"),
    ("The Mindset Shift", "the deeper change in thinking the book invites"),
    ("Daily Habits That Help", "small repeatable routines that put the ideas to work"),
    ("Lessons For Work And Life", "how the ideas apply to career, money, relationships and growth"),
    ("The Bigger Picture", "where the book sits among other important ideas"),
    ("Questions Worth Asking Yourself", "reflective questions that make the lessons personal"),
    ("What To Remember", "the handful of ideas that matter most"),
    ("Common Mistakes", "ways readers misunderstand or misuse the ideas"),
]
EXTRA_TOPICS = [
    ("Misconceptions Worth Clearing Up", "popular misunderstandings about the book and its ideas"),
    ("A Thirty Day Practice Plan", "a simple week-by-week way to apply the lessons"),
    ("When The Ideas Do Not Apply", "situations where the advice needs adjusting"),
    ("How To Explain These Ideas To Others", "explaining the key lessons simply to a friend or team"),
    ("Measuring Your Progress", "simple ways to notice whether the ideas are changing your results"),
    ("A Deeper Reflection", "the emotional and personal side of the book's message"),
    ("Long Term Thinking", "how the lessons compound over years"),
    ("Hypothetical Scenarios", "clearly hypothetical everyday situations that show the ideas at work"),
]


def wc(t):
    return len(t.split())


def tokens(t):
    return {w for w in re.findall(r"[a-z]{4,}", t.lower()) if w not in STOP}


def short_title(t):
    return " ".join(re.sub(r"[^\w\s'-]", "", t).split()[:6]).strip() or "Next Idea"


# ------------------------------------------------------------------ text hygiene
def clean_narration(t):
    t = re.sub(r"\*+|#+|_{2,}", "", t)
    t = re.sub(r"\b[Ii]n this (video|chapter|section|part|episode|talk),?\s*", "", t)
    lines = []
    for ln in t.splitlines():
        s = ln.strip()
        if not s:
            lines.append("")
            continue
        if re.match(r"^(chapter|section|part|narrator|host|voice ?over|title|note|layer)\b[^.]{0,50}[:\-]", s, re.I):
            continue
        if re.match(r"^[\[\(].{0,80}[\]\)]$", s):
            continue
        s = re.sub(r"^([-\u2022]|\d+[.)])\s+", "", s)
        lines.append(s)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def dedupe_sentences(text):
    seen, out = set(), []
    for para in re.split(r"\n\s*\n", text):
        keep = []
        for s in re.split(r"(?<=[.!?])\s+", para.strip()):
            k = re.sub(r"\W+", " ", s.lower()).strip()
            if len(k) > 25 and k in seen:
                continue
            seen.add(k)
            keep.append(s)
        if keep:
            out.append(" ".join(keep))
    return "\n\n".join(out)


class Guard:
    """Measures how many 7-word sequences of a text also appear in the research sources."""
    def __init__(self, texts, n=7):
        self.n, self.grams = n, set()
        for t in texts:
            w = re.findall(r"[a-z0-9']+", t.lower())
            for i in range(len(w) - n + 1):
                self.grams.add(hash(" ".join(w[i:i + n])))

    def overlap(self, text):
        w = re.findall(r"[a-z0-9']+", text.lower())
        total = len(w) - self.n + 1
        if total <= 0:
            return 0.0
        return sum(1 for i in range(total) if hash(" ".join(w[i:i + self.n])) in self.grams) / total


NUM = re.compile(r"\d[\d,]*\.?\d*%?")


def _num(n):
    return n.replace(",", "").rstrip(".")


class Facts:
    """STAGE 3 accuracy audit: a number or a quotation may only appear in the narration if the sources contain it."""
    def __init__(self, texts):
        flat = " ".join(texts).lower()
        self.flat = re.sub(r"\W+", " ", flat)
        self.nums = {_num(m) for m in NUM.findall(flat)}

    def supported(self, sentence):
        for n in NUM.findall(sentence):
            n2 = _num(n)
            if len(re.sub(r"\D", "", n2)) >= 2 and n2 not in self.nums:
                return False
        for q in re.findall(r"[\u201c\"]([^\u201d\"]{20,})[\u201d\"]", sentence):
            if re.sub(r"\W+", " ", q.lower()).strip() not in self.flat:
                return False
        return True

    def filter(self, text, log=None):
        out, dropped = [], 0
        for para in text.split("\n\n"):
            keep = []
            for s in re.split(r"(?<=[.!?])\s+", para.strip()):
                if s and self.supported(s):
                    keep.append(s)
                elif s:
                    dropped += 1
            if keep:
                out.append(" ".join(keep))
        if dropped and log:
            log(f"[qc] removed {dropped} sentence(s) with numbers/quotes that the sources do not contain")
        return "\n\n".join(out)


# ------------------------------------------------------------------ STAGE 1: ledger
def chunk_words(text, size=700):
    w = text.split()
    return [" ".join(w[i:i + size]) for i in range(0, len(w), size) if len(w[i:i + size]) > 120]


def pick_chunks(sources, limit):
    caps = {"wiki": 4, "video": 4, "web": 3, "book": 10, "pdf": 5}
    per = []
    for s in sources:
        ch = chunk_words(s["text"])
        cap = caps.get(s["kind"], 3)
        if len(ch) > cap:
            step = len(ch) / cap
            ch = [ch[int(i * step)] for i in range(cap)]
        per.append((s, ch))
    out, i = [], 0
    longest = max((len(ch) for _, ch in per), default=0)
    while len(out) < limit and i < longest:
        for s, ch in per:
            if i < len(ch) and len(out) < limit:
                out.append((s, ch[i]))
        i += 1
    return out


LEDGER_LINE = re.compile(r"^\W*(IDEA|WHY|HOW|EVIDENCE|EXAMPLE|PERSON|TERM|LIMIT|CONCLUSION)\W*[:\-]\s*(.+)$", re.I)


def extract_ledger(d, chunk):
    prompt = (f"Book: '{d['title']}' by {d['author']}.\nBelow is an excerpt from a source about this book or its subject. Build a "
              "coverage ledger of this excerpt. Write one line per item, each starting with one of these tags and a colon: "
              "IDEA (a main idea or argument), WHY (why it matters), HOW (the mechanism or a step of the reasoning), EVIDENCE "
              "(a study, data or historical fact), EXAMPLE (a story, case or analogy), PERSON (a named person and role), TERM "
              "(a technical term with a plain definition), LIMIT (an objection, exception or limitation), CONCLUSION (what "
              "the author concludes). Use YOUR OWN WORDS, one sentence per line, only information found in the excerpt. "
              "Write 6 to 12 lines.\n\nEXCERPT:\n" + chunk)
    out = local_ai.chat(prompt, system="You are a careful research analyst building an idea ledger.", max_tokens=520, temperature=0.3)
    items = []
    for ln in out.splitlines():
        m = LEDGER_LINE.match(ln.strip())
        if m and 25 <= len(m.group(2)) <= 340:
            items.append(dict(kind=m.group(1).upper(), note=m.group(2).strip()))
    return items


def dedupe_notes(notes):
    kept, sets = [], []
    for n in notes:
        t = tokens(n["note"])
        if not t or any(len(t & s) / max(len(t | s), 1) > 0.6 for s in sets):
            continue
        kept.append(n)
        sets.append(t)
    return kept


def build_ledger(d, sources, log):
    picks = pick_chunks(sources, config.MAX_NOTE_CHUNKS)
    notes = []
    for n, (s, chunk) in enumerate(picks, 1):
        if local_ai.time_left() < local_ai.budget_total() * 0.55:
            log("[ledger] research time share used up - moving on")
            break
        for g in extract_ledger(d, chunk):
            g["src"] = s["kind"]
            notes.append(g)
        if n % 5 == 0:
            log(f"[ledger] {n}/{len(picks)} excerpts read, {len(notes)} items")
    notes = dedupe_notes(notes)
    kinds = {}
    for x in notes:
        kinds[x["kind"]] = kinds.get(x["kind"], 0) + 1
    log(f"[ledger] {len(notes)} unique items: {kinds}")
    return notes


def glossary(notes, limit=18):
    g = [f"- {x['note']}" for x in notes if x["kind"] in ("TERM", "PERSON")][:limit]
    return "TERMINOLOGY AND PEOPLE (use these names and terms consistently):\n" + "\n".join(g) + "\n" if g else ""


# ------------------------------------------------------------------ STAGE 2: outline, assignment, writing
def make_outline(d, notes, n, log):
    sample = "\n".join(f"- {x['kind']}: {x['note']}" for x in notes[:70])
    prompt = (f"Plan a long audiobook-style adaptation of '{d['title']}' by {d['author']}.\nUsing the ledger, write exactly {n} "
              "chapter plans that cover the whole book. Follow the author's own order and structure when the ledger shows it; "
              "otherwise go from the core thesis, through each major idea or framework, the key stories and evidence, the "
              "objections and limits, to practical consequences. Give each chapter a short title (2 to 6 words) and a "
              "one-sentence focus.\nFormat strictly: one chapter per line as `Title | focus`. No numbering, no extra text."
              "\n\nLEDGER:\n" + sample)
    out = local_ai.chat(prompt, system="You are a thoughtful senior book editor.", max_tokens=1000, temperature=0.5)
    plan = []
    for ln in out.splitlines():
        if "|" in ln:
            t, f = ln.split("|", 1)
            t = re.sub(r"^[\s\d.)\-*]+|[`*\"]", "", t).strip()
            if 2 <= len(t) <= 70 and len(f.strip()) > 8:
                plan.append(dict(title=short_title(t), focus=f.strip().strip("`")))
    seen = {p["title"].lower() for p in plan}
    for t, f in GENERIC_CHAPTERS:
        if len(plan) >= n:
            break
        if t.lower() not in seen:
            plan.append(dict(title=t, focus=f))
    log(f"[outline] {len(plan[:n])} chapters: {[p['title'] for p in plan[:n]]}")
    return plan[:n]


def assign_notes(plan, notes, per=10):
    use = {i: 0 for i in range(len(notes))}
    nt = [tokens(n["note"]) for n in notes]
    out = []
    for ch in plan:
        want = tokens(ch["title"] + " " + ch["focus"])
        score = lambda i: len(want & nt[i]) * 2 - use[i] * 3 + random.random()
        ranked = sorted(range(len(notes)), key=lambda i: -score(i))
        pick = ranked[:per]
        for kind in ("EVIDENCE", "EXAMPLE", "LIMIT", "HOW", "WHY"):   # every layer of the seven-layer method needs material
            if not any(notes[i]["kind"] == kind for i in pick):
                extra = next((i for i in ranked if notes[i]["kind"] == kind and i not in pick), None)
                if extra is not None:
                    pick.append(extra)
        for i in pick:
            use[i] += 1
        out.append([notes[i] for i in pick])
    return out


def fmt_items(items):
    return "\n".join(f"{x['kind']}: {x['note']}" for x in items)


def ctx_for(d, notes, sources):
    guide = GENRE_GUIDE.get(d.get("category", ""), DEFAULT_GUIDE)
    if d.get("rights") == "public_domain":
        rights = "This is a faithful adaptation of a public-domain book: preserve the author's reasoning, examples and conclusions."
    else:
        rights = ("This is an original critical explanation of the book for listeners: explain and discuss its ideas in your own "
                  "words and never reproduce the book's text.")
    return dict(guide=guide, rights=rights, gloss=glossary(notes), facts=Facts([s["text"] for s in sources]))


def audit_and_fix(d, items, text, cx, log):
    """STAGE 3 depth audit: which ledger points are missing or only touched with a vague phrase? Add them."""
    if local_ai.time_left() < 600 or not items:
        return text
    pts = "\n".join(f"{i + 1}. {x['note']}" for i, x in enumerate(items))
    ans = local_ai.chat("Below is a numbered list of points from the source and a narration. Which numbered points are missing from "
                        "the narration, or covered only by one vague phrase? Answer ONLY with the numbers separated by commas, "
                        "or NONE.\n\nPOINTS:\n" + pts + "\n\nNARRATION:\n" + text,
                        system="You are a strict quality-control editor.", max_tokens=40, temperature=0.1)
    nums = [] if "NONE" in ans.upper() else [int(x) for x in re.findall(r"\d+", ans)]
    miss = [items[n - 1] for n in nums if 1 <= n <= len(items)][:5]
    if not miss:
        return text
    log(f"[qc] depth audit: {len(miss)} ledger point(s) were too thin - adding them")
    tail = " ".join(text.split()[-60:])
    more = clean_narration(local_ai.chat(
        f"{STYLE}\n{SEVEN}\n{cx['guide']}\n\nBOOK: '{d['title']}' by {d['author']}\nThe narration so far ended with: \"{tail}\"\n\n"
        f"Continue it with 150 to 250 words that cover ONLY these points clearly and in depth, in the same spoken voice:\n"
        f"{fmt_items(miss)}", system=SYS, max_tokens=520))
    more = cx["facts"].filter(dedupe_sentences(more))
    return text + "\n\n" + more if wc(more) > 60 else text


def generate(d, brief, items, prev_tail, target, guard, cx, log, audit=True):
    base = (f"{STYLE}\n{SEVEN}\n{AVOID}\n{cx['guide']}\n{cx['rights']}\n\nBOOK: '{d['title']}' by {d['author']}\nTHIS PART: {brief}\n\n"
            f"LEDGER (the facts you may use):\n{fmt_items(items)}\n\n{cx['gloss']}")
    if prev_tail:
        base += f"\nThe narration so far ended with: \"{prev_tail}\"\nContinue smoothly from there without recapping.\n"
    text = clean_narration(local_ai.chat(base + f"\nWrite about {target} words of narration for this part now. Begin directly "
                                         "with the narration.", system=SYS, max_tokens=min(int(target * 1.9) + 200, 1900)))
    tries = 0
    while wc(text) < target * 0.85 and tries < 3 and local_ai.time_left() > 600:
        tail = " ".join(text.split()[-200:])
        more = local_ai.chat(f"{STYLE}\n{SEVEN}\n{cx['guide']}\n\nBOOK: '{d['title']}' by {d['author']}\nTHIS PART: {brief}\n\n"
                             f"LEDGER:\n{fmt_items(items)}\n\nHere is the narration so far:\n\"{tail}\"\n\nContinue it smoothly for "
                             f"about 400 more words using ledger points not yet explained in depth. Do not repeat earlier "
                             f"sentences and do not wrap up the whole talk.", system=SYS, max_tokens=800)
        text = text + "\n\n" + clean_narration(more)
        tries += 1
    text = dedupe_sentences(text)
    if wc(text) > target * 1.35:  # a chatty model must not blow the 2-hour limit: keep whole paragraphs only
        kept, n = [], 0
        for p in text.split("\n\n"):
            if kept and n + wc(p) > target * 1.25:
                break
            kept.append(p)
            n += wc(p)
        text = "\n\n".join(kept)
    text = cx["facts"].filter(text, log)
    if audit:
        text = audit_and_fix(d, items, text, cx, log)
    if guard.overlap(text) > 0.05 and local_ai.time_left() > 400:
        log("[qc] text too close to the sources - rewriting in fresh words")
        again = clean_narration(local_ai.chat(
            "Rewrite the narration below completely in new words and a new sentence structure. Keep every point, keep the length, "
            "keep it spoken and flowing, and add nothing that is not already in it.\n\n" + text, system=SYS,
            max_tokens=min(int(wc(text) * 1.7) + 100, 2000), temperature=0.85))
        if wc(again) > wc(text) * 0.6:
            text = cx["facts"].filter(dedupe_sentences(again))
    return text


def tail_of(text, n=45):
    return " ".join(text.split()[-n:])


def write_long(d, sources, log=print):
    guard = Guard([s["text"] for s in sources])
    notes = build_ledger(d, sources, log)
    if len(notes) < 25:
        log("[ai] too few ledger items to write a long script")
        return None
    cx = ctx_for(d, notes, sources)
    log(f"[stage1] rights mode: {d.get('rights', 'analysis')} | genre guide: {d.get('category')}")
    n = max(10, math.ceil((config.LONG_TARGET_WORDS - 850) / 950))
    plan = make_outline(d, notes, n, log)
    assigned = assign_notes(plan, notes)
    per = max(700, min(int((config.LONG_TARGET_WORDS - 850) / len(plan)), 1100))

    secs = [dict(title="Introduction", text=generate(
        d, "OPENING. Begin with the real problem or question the book addresses, in a way that creates genuine curiosity without "
           "artificial drama, then say plainly what the book argues and what the listener will understand by the end. Do not "
           "greet the audience and do not announce a video.", notes[:10], "", 380, guard, cx, log, audit=False))]
    total = wc(secs[0]["text"])
    for i, (ch, nts) in enumerate(zip(plan, assigned), 1):
        if local_ai.time_left() < 900:
            log("[write] AI time budget almost used - stopping chapters here")
            break
        if total + per + 450 > config.LONG_MAX_WORDS:
            log("[write] reached the 2-hour length limit - stopping chapters here")
            break
        log(f"[write] chapter {i}/{len(plan)}: {ch['title']}  (total so far {total} words, {local_ai.time_left() / 60:.0f} min left)")
        txt = generate(d, f"{ch['title']} - {ch['focus']}", nts, tail_of(secs[-1]["text"]), per, guard, cx, log)
        secs.append(dict(title=ch["title"], text=txt))
        total += wc(txt)
    extras = EXTRA_TOPICS[:]
    while total < config.LONG_MIN_WORDS and extras and local_ai.time_left() > 900 and total + per + 450 < config.LONG_MAX_WORDS:
        t, f = extras.pop(0)
        log(f"[write] extra chapter: {t}  (total {total} words)")
        idx = random.sample(range(len(notes)), min(12, len(notes)))
        txt = generate(d, f"{t} - {f}", [notes[i] for i in idx], tail_of(secs[-1]["text"]), per, guard, cx, log)
        secs.append(dict(title=t, text=txt))
        total += wc(txt)
    secs.append(dict(title="Final Thoughts", text=generate(
        d, "CLOSING. Bring the book's main ideas together, say what follows from them, and finish with one thoughtful question or "
           "challenge for the listener and a memorable but honest last line. Include one warm sentence inviting them to like, "
           "subscribe and share this with a friend who needs it.", notes[:12], tail_of(secs[-1]["text"]), 420, guard, cx, log,
        audit=False)))
    total += wc(secs[-1]["text"])
    log(f"[write] DONE: {len(secs)} sections, {total} words (~{total / 143:.0f} min of narration)")
    d["concepts"] = [dict(term=s["title"], text=" ".join(s["text"].split()[:230])) for s in secs[1:-1] if wc(s["text"]) > 150]
    return secs


def write_short(d, term, excerpt):
    prompt = (f"{STYLE}\n{AVOID}\n\nWrite a YouTube Shorts narration of about 125 words (roughly 50 seconds) about ONE idea: {term}. It "
              f"comes from the book '{d['title']}' by {d['author']}. Base it ONLY on this material:\n{excerpt}\n\nStructure: a "
              "truthful, gripping first line, the idea explained simply with the example if the material has one, one genuine "
              "insight, and a last line that makes people want to replay it. Short sentences. Mention the book once.")
    text = clean_narration(local_ai.chat(prompt, system=SYS, max_tokens=420, temperature=0.8))
    return text if 70 <= wc(text) <= 200 else None
