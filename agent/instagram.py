"""Publishes a Reel through the Instagram API with Instagram Login."""
import time

import requests

from . import config

GRAPH = "https://graph.instagram.com"


def publish_reel(video_url, caption):
    tok = config.IG_TOKEN
    r = requests.post(f"{GRAPH}/{config.IG_USER_ID}/media", data={
        "media_type": "REELS", "video_url": video_url, "caption": caption,
        "share_to_feed": "true", "access_token": tok}, timeout=60)
    r.raise_for_status()
    container = r.json()["id"]

    for _ in range(15):                         # wait up to ~7.5 minutes for Instagram to process
        time.sleep(30)
        s = requests.get(f"{GRAPH}/{container}", params={"fields": "status_code,status",
                                                         "access_token": tok}, timeout=30).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram could not process the video: {s}")
    else:
        raise RuntimeError("Instagram took too long to process the video")

    r = requests.post(f"{GRAPH}/{config.IG_USER_ID}/media_publish",
                      data={"creation_id": container, "access_token": tok}, timeout=60)
    r.raise_for_status()
    media_id = r.json()["id"]
    link = requests.get(f"{GRAPH}/{media_id}", params={"fields": "permalink", "access_token": tok},
                        timeout=30).json().get("permalink", "")
    return media_id, link


def refresh_token():
    """Long-lived tokens last 60 days; refreshing returns a token valid for another 60."""
    r = requests.get(f"{GRAPH}/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": config.IG_TOKEN}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def weekly_stats(days=7):
    since = int(time.time()) - days * 86400
    r = requests.get(f"{GRAPH}/{config.IG_USER_ID}/media", params={
        "fields": "caption,permalink,timestamp,like_count,comments_count",
        "since": since, "access_token": config.IG_TOKEN}, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])
