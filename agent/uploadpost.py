"""Publishes a Reel through Upload-Post (upload-post.com), which has its own approved Meta app."""
import time

import requests

from . import config

API = "https://api.upload-post.com/api"


def _headers():
    return {"Authorization": f"Apikey {config.UPLOADPOST_API_KEY}"}


def _find_url(data):
    """Digs the Instagram post link out of a response, wherever it sits."""
    if isinstance(data, dict):
        for k, v in data.items():
            if k == "url" and isinstance(v, str) and v.startswith("http"):
                return v
            found = _find_url(v)
            if found:
                return found
    if isinstance(data, list):
        for v in data:
            found = _find_url(v)
            if found:
                return found
    return ""


def publish_reel(video_path, caption, post_id, platforms=("instagram",)):
    with open(video_path, "rb") as f:
        r = requests.post(f"{API}/upload", headers={**_headers(), "Idempotency-Key": post_id}, data={
            "user": config.UPLOADPOST_USER,
            "platform[]": list(platforms),
            "title": caption,
            "media_type": "REELS",
            "share_to_feed": "true",
            "request_id": post_id,
        }, files={"video": f}, timeout=600)
    data = r.json() if r.content else {}
    if r.status_code == 429:
        raise RuntimeError("Upload-Post monthly limit reached. Upgrade the plan or wait for next month.")
    if r.status_code == 403:
        raise RuntimeError(f"Upload-Post plan does not allow this (TikTok needs a paid plan): {str(data)[:300]}")
    if not r.ok or not data.get("success", False):
        raise RuntimeError(f"Upload-Post refused the post ({r.status_code}): {str(data)[:500]}")
    link = _find_url(data)
    if link or "results" in data:
        return post_id, link
    # Processed in the background: check its status for up to 10 minutes.
    req = data.get("request_id", post_id)
    for _ in range(20):
        time.sleep(30)
        s = requests.get(f"{API}/uploadposts/status", headers=_headers(),
                         params={"request_id": req}, timeout=30).json()
        link = _find_url(s)
        text = str(s).lower()
        if link or "completed" in text or "'success': true" in text and "pending" not in text:
            return post_id, link
        if "fail" in text or "error" in text:
            raise RuntimeError(f"Upload-Post could not publish: {str(s)[:500]}")
    return post_id, ""                              # still processing; it usually appears shortly
