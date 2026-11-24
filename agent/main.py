"""Entry point. GitHub Actions runs one of:
    python -m agent.main poll     # every 15 min: read buttons, post approved Reels,
                                  #   and each morning design the day's Reel
    python -m agent.main make     # design a Reel right now (manual)
    python -m agent.main refresh  # weekly: renew the Instagram token, send stats
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from . import buffer, config, designer, instagram, quran, telegram, uploadpost

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "queue.json")
STATE = os.path.join(ROOT, "state.json")
MEDIA = os.path.join(ROOT, "media")


def load(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_caption(item, reciter, reference):
    return "\n\n".join([
        item["caption_en"],
        item["caption_pl"],
        f"📖 {reference}\n🎙 {reciter}\n🌐 {config.TRANSLATION_CREDIT}",
        config.HASHTAGS,
    ])


def build_caption_x(item, reciter, reference):
    """X allows 280 characters: the English line, the reference and two hashtags."""
    tail = f"\n\n📖 {reference} · {reciter}\n#quran #islam"
    text = item["caption_en"]
    if len(text) + len(tail) > 280:
        text = text[:280 - len(tail) - 1].rsplit(" ", 1)[0] + "…"
    return text + tail


def video_name(post_id, variant):
    return f"{post_id}-v{variant}.mp4"          # new name per design, so no stale cached copy is posted


def video_url(post_id, variant):
    return f"https://raw.githubusercontent.com/{config.REPO}/{config.BRANCH}/media/{video_name(post_id, variant)}"


# ---------- make ----------

def make(state, variant=0, item=None):
    """variant counts redesigns of the same Reel: each one uses the next Canva background."""
    if not config.TELEGRAM_CHAT_ID:
        raise RuntimeError("Add the TELEGRAM_CHAT_ID secret first (message the bot, then run poll).")
    queue = load(QUEUE, [])
    if item is None:
        if state.get("pending"):
            return                                   # one Reel awaits a decision; don't pile up
        item = next((q for q in queue if q.get("status", "queued") == "queued"), None)
        if item is None:
            telegram.send_text("The queue is empty. Ask Claude for the next batch of Reels.")
            return
        state["reciter_i"] = state.get("reciter_i", -1) + 1
        state["bg_i"] = state.get("bg_i", -1) + 1
    names = list(config.RECITERS)
    reciter = item.get("reciter") or names[state.get("reciter_i", 0) % len(names)]
    text = quran.fetch_text(item["key"])
    os.makedirs(MEDIA, exist_ok=True)
    _remove_video(item["id"])
    out = os.path.join(MEDIA, video_name(item["id"], variant))
    with tempfile.TemporaryDirectory() as tmp:
        audio = os.path.join(tmp, "recitation.mp3")
        durations = quran.fetch_audio(item["key"], reciter, audio)
        # each Reel starts a few scenes further on, and "New design" moves on again
        start = (state.get("bg_i", 0) * 5 + variant * 3)
        seconds = designer.render(durations, audio, out, start=start)
    caption = build_caption(item, reciter, text["reference"])
    msg_id = telegram.send_for_approval(
        out, f"New Reel ready: {text['reference']} · {reciter} · {seconds:.0f}s\n\n{caption}", item["id"])
    state["last_made"] = datetime.now(ZoneInfo(config.TIMEZONE)).date().isoformat()
    weekday = datetime.now(ZoneInfo(config.TIMEZONE)).weekday()
    platforms = [p for p, days in config.POST_DAYS.items() if weekday in days] or ["instagram"]
    if config.POSTER != "buffer":                # TikTok and X are only posted through Buffer
        platforms = ["instagram"]
    state["pending"] = {"id": item["id"], "message_id": msg_id, "variant": variant, "platforms": platforms,
                        "caption": caption, "caption_x": build_caption_x(item, reciter, text["reference"]),
                        "title": text["reference"], "status": "waiting", "reciter": reciter}


# ---------- poll ----------

def set_status(post_id, status, **extra):
    queue = load(QUEUE, [])
    for q in queue:
        if q["id"] == post_id:
            q["status"] = status
            q.update(extra)
    save(QUEUE, queue)


def handle_message(msg, state):
    chat = str(msg["chat"]["id"])
    if not config.TELEGRAM_CHAT_ID:
        telegram.send_text(f"Hi! Your chat ID is {chat}. Add it to GitHub as the secret TELEGRAM_CHAT_ID.", chat)
        return
    if chat != config.TELEGRAM_CHAT_ID:
        return                                       # ignore everyone except the approver
    if msg.get("video") or msg.get("photo") or msg.get("document"):
        handle_upload(msg, state)
        return
    text = msg.get("text", "")
    if text.startswith("/new"):
        pending = state.get("pending")
        if pending and pending["status"] == "waiting":
            telegram.send_text("A Reel is already waiting for you: tap 🔄 New design (same verses) "
                               "or ❌ Skip (next verses) under it.")
        elif pending:
            telegram.send_text("The approved Reel hasn't been posted yet. Send /postnow to post it first.")
        else:
            telegram.send_text("🎬 Making a new Reel. It arrives in about 3 minutes.")
            make(state)
        return
    if text.startswith("/help") or text.startswith("/start"):
        telegram.send_text("Commands\n/new: make a new Reel now\n/postnow: post the approved Reel now\n"
                           "/status: queue and posting accounts\n\nSend a video or photo to post it.\n"
                           "Under each Reel: ✅ Post at 19:00 · 🚀 Post now · 🔄 New design · ❌ Skip")
        return
    if msg.get("text", "").startswith("/postnow"):
        pending = state.get("pending")
        if pending and pending["status"] in ("approved", "waiting"):
            pending["status"] = "approved"              # /postnow also approves a waiting Reel
            pending["now"] = True
            telegram.send_text("🚀 Posting the Reel now. The links follow in a few minutes.")
        else:
            telegram.send_text("No approved Reel is waiting.")
        return
    if msg.get("text", "").startswith("/status"):
        queue = load(QUEUE, [])
        left = sum(1 for q in queue if q.get("status", "queued") == "queued")
        posted = sum(1 for q in queue if q.get("status") == "posted")
        via = config.POSTER
        if via == "buffer":
            try:
                names = ", ".join(NAMES.get(p, p) for p in buffer.channels())
                via = f"Buffer → {names}" if names else buffer.diagnose()
            except RuntimeError as e:
                via = f"Buffer ⚠️ {e}"
        telegram.send_text(f"Posted: {posted}\nWaiting in queue: {left}\nPosting via: {via}")


def handle_button(cb, state):
    if str(cb["message"]["chat"]["id"]) != config.TELEGRAM_CHAT_ID:
        return
    action, _, post_id = cb["data"].partition(":")
    if action == "up":
        choice, _, uid = post_id.partition(":")
        handle_upload_button(cb, state, choice, uid)
        return
    pending = state.get("pending")
    if not pending or pending["id"] != post_id or pending["status"] != "waiting":
        telegram.answer(cb["id"], "This Reel was already handled.")
        return
    queue = load(QUEUE, [])
    item = next(q for q in queue if q["id"] == post_id)
    if action == "now":
        pending["status"] = "approved"
        pending["now"] = True
        telegram.answer(cb["id"], "Posting now")
        telegram.clear_buttons(pending["message_id"], "🚀 Approved. Posting now; the links follow in a few minutes.")
    elif action == "approve":
        pending["status"] = "approved"
        telegram.answer(cb["id"], "Approved")
        telegram.clear_buttons(pending["message_id"],
                               f"✅ Approved for {', '.join(pending.get('platforms', ['instagram']))}. "
                               f"It goes live at {config.POST_HOUR}:00 (or now, if that time has passed).")
    elif action == "redesign":
        telegram.answer(cb["id"], "Making a new design…")
        telegram.clear_buttons(pending["message_id"], "🔄 Making a new design. It arrives in a few minutes.")
        state["pending"] = None
        make(state, variant=pending["variant"] + 1, item={**item, "reciter": pending.get("reciter")})
    elif action == "skip":
        telegram.answer(cb["id"], "Skipped")
        telegram.clear_buttons(pending["message_id"], "❌ Skipped. Sending the next Reel.")
        set_status(post_id, "skipped")
        _remove_video(post_id)
        state["pending"] = None
        make(state)


def _remove_video(post_id):
    if os.path.isdir(MEDIA):
        for name in os.listdir(MEDIA):
            if name.startswith(f"{post_id}-v"):
                os.remove(os.path.join(MEDIA, name))


NAMES = {"instagram": "Instagram", "tiktok": "TikTok", "x": "X"}


def buffer_job(state, job, url, kind="video"):
    """Posts one item to each of job["platforms"] that is connected in Buffer, once.
    Safe to call again: a platform that already has a Buffer post is never posted twice.
    Returns report lines when every platform is finished, else None (checked again next run)."""
    posts = job.setdefault("buffer_posts", {})          # platform -> Buffer post id | "unknown"
    done = job.setdefault("done", {})                   # platform -> link | "error: ..." | "unknown"
    errors = job.setdefault("errors", {})
    if "connected" not in job:
        chans = buffer.channels()
        job["connected"] = chans
        for p in job["platforms"]:
            if p not in chans:
                done[p] = "not connected in Buffer"
    chans = job["connected"]
    for p in job["platforms"]:
        if p in done or p in posts or p not in chans:
            continue
        text = (job.get("caption_x") or job["caption"][:280]) if p == "x" else job["caption"]
        try:
            posts[p] = buffer.create(p, chans[p], text, url, job.get("title", ""), kind)
        except buffer.Unsure as e:
            posts[p] = "unknown"
            done[p] = f"unknown ({e}) - check the app before posting again"
        except RuntimeError as e:
            errors[p] = errors.get(p, 0) + 1
            if errors[p] >= 3:
                done[p] = f"error: {e}"
        save(STATE, state)                              # record each post at once (no doubles)
    waiting = {p: i for p, i in posts.items() if p not in done and i != "unknown"}
    for p, (st, info) in buffer.wait(waiting).items():
        if st == "sent":
            done[p] = info or "posted"
        elif st == "error":
            done[p] = f"error: {info}"
    if any(p not in done for p in job["platforms"]):
        return None
    lines = []
    for p in job["platforms"]:
        r = done[p]
        ok = r.startswith("http") or r == "posted"
        icon = "✅" if ok else ("➖" if r.startswith("not connected") else "⚠️")
        lines.append(f"{icon} {NAMES.get(p, p)}: {r}")
    if any(not (d.startswith("http") or d == "posted" or d.startswith("not connected")) for d in done.values()):
        lines.append("\nFor ⚠️ platforms, post it by hand from the message above.")
    return lines


def publish_buffer(state, pending):
    pending["status"] = "publishing"
    lines = buffer_job(state, pending, video_url(pending["id"], pending["variant"]))
    if lines is None:
        return                                          # still processing: checked again next run
    set_status(pending["id"], "posted", media_id=str(pending.get("buffer_posts")),
               posted_at=datetime.utcnow().isoformat())
    _remove_video(pending["id"])
    state["pending"] = None
    telegram.send_text("🎉 Reel published\n" + "\n".join(lines))


# ---------- your own uploads: send a video or photo to the bot ----------

def git_save(paths, message):
    """Pushes files now, so Buffer can download them from the public repository."""
    def git(*a):
        subprocess.run(["git", *a], cwd=ROOT, check=True, capture_output=True, text=True)
    git("add", "-A", *paths)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
        return
    git("-c", "user.name=reel-agent", "-c", "user.email=reel-agent@users.noreply.github.com",
        "commit", "-q", "-m", message)
    git("pull", "-q", "--rebase", "--autostash", "origin", config.BRANCH)
    git("push", "-q", "origin", f"HEAD:{config.BRANCH}")


def raw_url(name):
    return f"https://raw.githubusercontent.com/{config.REPO}/{config.BRANCH}/media/{name}"


def handle_upload(msg, state):
    """A video or photo from the approver: ask where to post it (nothing is posted without a tap)."""
    if msg.get("video"):
        f, kind, ext = msg["video"], "video", ".mp4"
    elif msg.get("photo"):
        f, kind, ext = msg["photo"][-1], "image", ".jpg"          # largest size
    else:
        d = msg["document"]
        mime = d.get("mime_type", "")
        if not mime.startswith(("video/", "image/")):
            telegram.send_text("Send a video or a photo and I'll post it.")
            return
        f, kind = d, ("video" if mime.startswith("video/") else "image")
        ext = ".mp4" if kind == "video" else (".png" if "png" in mime else ".jpg")
    if f.get("file_size", 0) > 20 * 1024 * 1024:
        telegram.send_text("This file is over 20 MB, the most a Telegram bot can download. "
                           "Send a shorter or compressed version.")
        return
    uid = f"u{msg['message_id']}"
    state.setdefault("uploads", {})[uid] = {
        "file_id": f["file_id"], "kind": kind, "ext": ext, "caption": msg.get("caption") or config.HASHTAGS,
        "status": "asking"}
    options = [("📤 Instagram", f"up:ig:{uid}")]
    if kind == "video" and config.POSTER == "buffer":
        options.append(("📤 Instagram + TikTok + X", f"up:all:{uid}"))
    options.append(("✖ Cancel", f"up:no:{uid}"))
    note = "" if msg.get("caption") else "\n(No caption was sent, so only your hashtags will be used.)"
    state["uploads"][uid]["ask_id"] = telegram.ask(f"Post this {kind} now?{note}", options)


def handle_upload_button(cb, state, choice, uid):
    job = state.get("uploads", {}).get(uid)
    if not job or job["status"] != "asking":
        telegram.answer(cb["id"], "Already handled.")
        return
    telegram.clear_buttons(job["ask_id"], "✖ Cancelled." if choice == "no" else "📤 Posting now…")
    telegram.answer(cb["id"], "OK")
    if choice == "no":
        state["uploads"].pop(uid)
        return
    if config.POSTER != "buffer":
        state["uploads"].pop(uid)
        telegram.send_text("Posting your own files needs Buffer: add the BUFFER_API_KEY secret on GitHub.")
        return
    job["platforms"] = ["instagram"] if choice == "ig" else ["instagram", "tiktok", "x"]
    job["status"] = "posting"
    job["name"] = f"{uid}{job['ext']}"
    os.makedirs(MEDIA, exist_ok=True)
    telegram.download(job["file_id"], os.path.join(MEDIA, job["name"]))
    git_save(["media"], f"Upload {uid} for posting")
    save(STATE, state)


def process_uploads(state):
    for uid, job in list(state.get("uploads", {}).items()):
        if job["status"] != "posting":
            continue
        lines = buffer_job(state, job, raw_url(job["name"]), job["kind"])
        if lines is None:
            continue
        path = os.path.join(MEDIA, job["name"])
        if os.path.exists(path):
            os.remove(path)
        state["uploads"].pop(uid)
        telegram.send_text("🎉 Your post is published\n" + "\n".join(lines))


def publish_if_due(state):
    pending = state.get("pending")
    if not pending or pending["status"] not in ("approved", "publishing"):
        return
    if (pending["status"] == "approved" and not pending.get("now")
            and datetime.now(ZoneInfo(config.TIMEZONE)).hour < config.POST_HOUR):
        return
    if config.POSTER == "buffer":
        publish_buffer(state, pending)
        return
    if config.POSTER == "meta":
        media_id, link = instagram.publish_reel(video_url(pending["id"], pending["variant"]), pending["caption"])
    else:
        path = os.path.join(MEDIA, video_name(pending["id"], pending["variant"]))
        media_id, link = uploadpost.publish_reel(path, pending["caption"], pending["id"],
                                                 pending.get("platforms", ["instagram"]))
    set_status(pending["id"], "posted", media_id=media_id, posted_at=datetime.utcnow().isoformat())
    _remove_video(pending["id"])
    state["pending"] = None
    where = " and ".join(p.capitalize() if p != "tiktok" else "TikTok" for p in pending.get("platforms", ["instagram"]))
    telegram.send_text(f"🎉 Posted on {where}: {link}" if link else f"🎉 Sent to {where}. It appears within a few minutes.")


def poll_once(state, wait):
    try:
        updates = telegram.get_updates(state.get("offset", 0), wait)
    except requests.RequestException:
        time.sleep(5)                                # a network blip: try again on the next round
        updates = []
    for u in updates:
        state["offset"] = u["update_id"] + 1
        if "message" in u:
            handle_message(u["message"], state)
        elif "callback_query" in u:
            handle_button(u["callback_query"], state)
        save(STATE, state)
    publish_if_due(state)
    process_uploads(state)
    if not config.TELEGRAM_CHAT_ID:
        return                                   # no approver connected yet: nothing to send to
    now = datetime.now(ZoneInfo(config.TIMEZONE))
    if (now.weekday() in config.POST_WEEKDAYS and now.hour >= config.MAKE_HOUR
            and state.get("last_made") != now.date().isoformat()):
        make(state)                              # the day's Reel, once per day
    save(STATE, state)


def poll(state):
    """Stays connected to Telegram for a few minutes, so button presses are answered in seconds."""
    deadline = time.time() + 60 * float(os.environ.get("POLL_MINUTES", "0"))
    poll_once(state, 0)
    while time.time() + 55 < deadline:
        poll_once(state, 50)


# ---------- refresh ----------

def refresh():
    if config.POSTER != "meta" or not config.IG_TOKEN:
        return                                   # only the Meta route has a token to renew
    new = instagram.refresh_token()
    print(f"::add-mask::{new}")                 # hide the token in GitHub's logs
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f:
        f.write(f"token={new}\n")               # the workflow saves it back as the IG_TOKEN secret
    posts = instagram.weekly_stats()
    if posts:
        best = max(posts, key=lambda p: p.get("like_count", 0) + 3 * p.get("comments_count", 0))
        likes = sum(p.get("like_count", 0) for p in posts)
        comments = sum(p.get("comments_count", 0) for p in posts)
        telegram.send_text(f"📊 This week: {len(posts)} Reels, {likes} likes, {comments} comments.\n"
                           f"Best: {best.get('permalink', '')}")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "poll"
    state = load(STATE, {})
    try:
        if cmd == "make":
            make(state)
        elif cmd == "poll":
            poll(state)
        elif cmd == "refresh":
            refresh()
    except Exception:
        err = traceback.format_exc()
        print(err)
        if config.TELEGRAM_CHAT_ID:
            telegram.send_text(f"⚠️ Something went wrong ({cmd}). Send this to Claude:\n\n{err[-1500:]}")
        raise
    finally:
        save(STATE, state)


if __name__ == "__main__":
    main()
