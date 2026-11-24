"""Entry point. GitHub Actions runs one of:
    python -m agent.main poll     # every 15 min: read buttons, post approved Reels,
                                  #   and each morning design the day's Reel
    python -m agent.main make     # design a Reel right now (manual)
    python -m agent.main refresh  # weekly: renew the Instagram token, send stats
"""
import json
import os
import sys
import tempfile
import time
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config, designer, instagram, quran, telegram, uploadpost

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
    state["pending"] = {"id": item["id"], "message_id": msg_id, "variant": variant, "platforms": platforms,
                        "caption": caption, "status": "waiting", "reciter": reciter}


# ---------- poll ----------

def set_status(post_id, status, **extra):
    queue = load(QUEUE, [])
    for q in queue:
        if q["id"] == post_id:
            q["status"] = status
            q.update(extra)
    save(QUEUE, queue)


def handle_message(msg):
    chat = str(msg["chat"]["id"])
    if not config.TELEGRAM_CHAT_ID:
        telegram.send_text(f"Hi! Your chat ID is {chat}. Add it to GitHub as the secret TELEGRAM_CHAT_ID.", chat)
        return
    if chat != config.TELEGRAM_CHAT_ID:
        return                                       # ignore everyone except the approver
    if msg.get("text", "").startswith("/status"):
        queue = load(QUEUE, [])
        left = sum(1 for q in queue if q.get("status", "queued") == "queued")
        posted = sum(1 for q in queue if q.get("status") == "posted")
        telegram.send_text(f"Posted: {posted}\nWaiting in queue: {left}")


def handle_button(cb, state):
    if str(cb["message"]["chat"]["id"]) != config.TELEGRAM_CHAT_ID:
        return
    action, _, post_id = cb["data"].partition(":")
    pending = state.get("pending")
    if not pending or pending["id"] != post_id or pending["status"] != "waiting":
        telegram.answer(cb["id"], "This Reel was already handled.")
        return
    queue = load(QUEUE, [])
    item = next(q for q in queue if q["id"] == post_id)
    if action == "approve":
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


def publish_if_due(state):
    pending = state.get("pending")
    if not pending or pending["status"] != "approved":
        return
    if datetime.now(ZoneInfo(config.TIMEZONE)).hour < config.POST_HOUR:
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
    for u in telegram.get_updates(state.get("offset", 0), wait):
        state["offset"] = u["update_id"] + 1
        if "message" in u:
            handle_message(u["message"])
        elif "callback_query" in u:
            handle_button(u["callback_query"], state)
        save(STATE, state)
    publish_if_due(state)
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
