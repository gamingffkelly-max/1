import os, sys, json
import brain, studio, rig, fx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

rig.install()  # human-like rigged characters + JPG files into out/
fx.install()   # podcast-style editing, paper evidence, music/SFX, varied thumbnails


def load_used():
    try:
        return json.load(open("used.json"))
    except Exception:
        return []


def save_used(u):
    json.dump(u[-600:], open("used.json", "w"))


def youtube():
    c = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=os.environ["YT_CLIENT_ID"],
                    client_secret=os.environ["YT_CLIENT_SECRET"])
    return build("youtube", "v3", credentials=c)


def upload(path, title, desc, tags, thumb=None):
    y = youtube()
    body = {"snippet": {"title": title[:100], "description": desc[:4900], "tags": tags,
                        "categoryId": "25", "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    req = y.videos().insert(part="snippet,status", body=body,
                            media_body=MediaFileUpload(path, chunksize=16 * 1024 * 1024,
                                                       resumable=True, mimetype="video/mp4"))
    resp = None
    while resp is None:
        st, resp = req.next_chunk()
        if st:
            print("upload", int(st.progress() * 100), "%", flush=True)
    vid = resp["id"]
    print("uploaded:", vid)
    if thumb:
        try:
            y.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb)).execute()
        except Exception as e:
            print("thumbnail failed (channel must be verified):", e)
    return vid


def main(kind):
    os.makedirs("out", exist_ok=True)
    prefix = {"long": "l", "short": "s", "friday": "f"}[kind]
    used = load_used()
    arts = brain.fetch_articles()
    h, main_art, group = brain.pick_topic(arts, used, prefix)
    topic = brain.clean_topic(main_art["title"])
    print("TOPIC:", topic, "| kind:", kind, flush=True)
    srcs = [{"name": a["source"], "date": a["date"], "title": a["title"]} for a in group]

    if kind == "long":
        lines = brain.write_script(topic, group, int(os.getenv("TARGET_MIN", "112")))
        studio.produce(lines, srcs, topic, 1280, 720, 15, "out/final.mp4")
        title, desc, tags = brain.seo(topic)
        studio.thumbnail(title, "out/thumb.jpg")
        upload("out/final.mp4", title, desc, tags, "out/thumb.jpg")
    elif kind == "short":
        lines = brain.write_short(topic, group)
        studio.produce(lines, srcs, topic, 1080, 1920, 15, "out/short.mp4", max_sec=58)
        title, desc, tags = brain.seo(topic, short=True)
        upload("out/short.mp4", title, desc, tags + ["shorts"])
    else:  # friday: text + image post (saved as artifact)
        text = brain.friday_text(topic)
        open("out/friday_post.txt", "w").write(text)
        studio.thumbnail(topic, "out/friday_post.jpg")
        print(text)

    used.append(h)
    save_used(used)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "long")
