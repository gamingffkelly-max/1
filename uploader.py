import time, os, requests
from config import *
API = "https://www.googleapis.com"

def _token():
    r = requests.post("https://oauth2.googleapis.com/token", timeout=60, data={"client_id": YT_CLIENT_ID, "client_secret": YT_CLIENT_SECRET,
                      "refresh_token": YT_REFRESH_TOKEN, "grant_type": "refresh_token"})
    r.raise_for_status(); return r.json()["access_token"]

def upload(video, title, desc, tags, thumb=None):
    H = {"Authorization": f"Bearer {_token()}"}; size = os.path.getsize(video)
    meta = {"snippet": {"title": title[:100], "description": desc[:4900], "tags": [t for t in tags][:25], "categoryId": YT_CATEGORY,
                        "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}}
    r = requests.post(f"{API}/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status", json=meta, timeout=120,
                      headers={**H, "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"})
    r.raise_for_status(); loc = r.headers["Location"]; CH = 32 * 1024 * 1024; pos = 0; vid = None
    with open(video, "rb") as f:
        while pos < size and not vid:
            f.seek(pos); data = f.read(CH); end = pos + len(data) - 1
            for a in range(8):
                try:
                    r = requests.put(loc, data=data, timeout=900, headers={"Content-Length": str(len(data)), "Content-Range": f"bytes {pos}-{end}/{size}"})
                    if r.status_code in (200, 201): vid = r.json()["id"]; break
                    if r.status_code == 308: break
                    if r.status_code < 500: r.raise_for_status()
                except requests.RequestException: pass
                time.sleep(2 ** a)
            else: raise RuntimeError("upload failed")
            pos = end + 1
    if thumb and vid:
        try:
            requests.post(f"{API}/upload/youtube/v3/thumbnails/set?videoId={vid}&uploadType=media", timeout=120,
                          headers={**H, "Content-Type": "image/jpeg"}, data=open(thumb, "rb").read()).raise_for_status()
        except Exception: pass
    return vid
