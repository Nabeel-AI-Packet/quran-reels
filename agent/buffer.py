"""Publishes a Reel to Instagram, TikTok and X through Buffer (buffer.com, free plan).

Buffer uses its own approved apps for every platform, so no Meta/TikTok/X developer app is
needed. You only connect your accounts in Buffer and add one secret: BUFFER_API_KEY.
The channels are found automatically - no IDs to copy.

Buffer downloads the video from a public link: the Reel's file in this (public) repository.
"""
import time

import requests

from . import config

API = "https://api.buffer.com"
SERVICES = {"instagram": "instagram", "tiktok": "tiktok", "twitter": "x", "x": "x"}

_ORGS = "query { account { organizations { id name } } }"
_CHANNELS = """query Channels($input: ChannelsInput!) {
  channels(input: $input) { id name service } }"""
_CREATE = """mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id status } }
    ... on MutationError { message } } }"""
_POST = """query GetPost($input: PostInput!) {
  post(input: $input) { id status externalLink error { message } } }"""


class Unsure(RuntimeError):
    """The request may have reached Buffer: never repeat it automatically."""


def _gql(query, variables=None, mutation=False):
    try:
        r = requests.post(API, json={"query": query, "variables": variables or {}}, timeout=60,
                          headers={"Authorization": f"Bearer {config.BUFFER_API_KEY}"})
    except requests.ConnectionError as e:
        raise RuntimeError(f"Buffer unreachable: {e}") from None
    except requests.Timeout:
        if mutation:
            raise Unsure("Buffer did not answer in time") from None
        raise RuntimeError("Buffer did not answer in time") from None
    if r.status_code == 401:
        raise RuntimeError("Buffer rejected the API key. Check the BUFFER_API_KEY secret.")
    if r.status_code == 429:
        raise RuntimeError("Buffer's free-plan request limit was reached; trying again later.")
    if r.status_code >= 500 and mutation:
        raise Unsure(f"Buffer error {r.status_code}")
    data = r.json() if r.content else {}
    if data.get("errors"):
        raise RuntimeError(f"Buffer error: {str(data['errors'])[:400]}")
    return data.get("data") or {}


def channels():
    """{'instagram': id, 'tiktok': id, 'x': id} for the accounts connected in Buffer."""
    found = {}
    for org in _gql(_ORGS).get("account", {}).get("organizations", []):
        for ch in _gql(_CHANNELS, {"input": {"organizationId": org["id"]}}).get("channels", []):
            platform = SERVICES.get(str(ch.get("service", "")).lower())
            if platform and platform not in found:
                found[platform] = ch["id"]
    return found


def _metadata(platform, title, kind="video"):
    if platform == "instagram":
        if kind == "image":
            return {"instagram": {"type": "post"}}
        return {"instagram": {"type": "reel", "shouldShareToFeed": True}}
    if platform == "tiktok":
        return {"tiktok": {"title": title[:90], "isAiGenerated": False}}
    return {}


def create(platform, channel_id, text, media_url, title, kind="video"):
    asset = {"image": {"url": media_url}} if kind == "image" else {"video": {"url": media_url}}
    res = _gql(_CREATE, {"input": {
        "channelId": channel_id, "text": text, "schedulingType": "automatic", "mode": "shareNow",
        "assets": [asset], "metadata": _metadata(platform, title, kind)}},
        mutation=True).get("createPost", {})
    if "post" not in res:
        raise RuntimeError(f"Buffer refused the {platform} post: {res.get('message', res)}")
    return res["post"]["id"]


def status(post_id):
    """('sent', link) | ('error', message) | ('pending', '')"""
    p = _gql(_POST, {"input": {"id": post_id}}).get("post") or {}
    if p.get("status") == "sent":
        return "sent", p.get("externalLink") or ""
    if p.get("status") == "error":
        return "error", (p.get("error") or {}).get("message", "unknown error")
    return "pending", ""


def wait(post_ids, minutes=8):
    """Checks every 30 s until each post is sent or failed, or time runs out."""
    results = {p: ("pending", "") for p in post_ids}
    deadline = time.time() + minutes * 60
    while time.time() < deadline and any(s == "pending" for s, _ in results.values()):
        time.sleep(30)
        for platform, pid in post_ids.items():
            if results[platform][0] == "pending":
                try:
                    results[platform] = status(pid)
                except RuntimeError:
                    pass
    return results


def diagnose():
    """Plain-language summary of what Buffer returned, for /status."""
    orgs = _gql(_ORGS).get("account", {}).get("organizations", [])
    if not orgs:
        return "Buffer returned no organization for this API key."
    parts = []
    for org in orgs:
        chans = _gql(_CHANNELS, {"input": {"organizationId": org["id"]}}).get("channels", [])
        found = ", ".join(f"{c.get('service')} ({c.get('name')})" for c in chans) or "no channels"
        parts.append(f"{org.get('name') or org['id']}: {found}")
    return "Buffer sees → " + "; ".join(parts)
