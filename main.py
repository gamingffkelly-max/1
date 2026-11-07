import sys, logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
from config import YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
import pipeline

kind = sys.argv[1] if len(sys.argv) > 1 else "short"
missing = [n for n, v in [("YT_CLIENT_ID", YT_CLIENT_ID), ("YT_CLIENT_SECRET", YT_CLIENT_SECRET), ("YT_REFRESH_TOKEN", YT_REFRESH_TOKEN)] if not v]
if missing: sys.exit(f"Missing GitHub Secrets: {', '.join(missing)}")
pipeline.build(kind)
