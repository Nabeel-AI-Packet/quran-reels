"""Minimal Telegram Bot API client."""
import json

import requests

from . import config


def _api(method, **kw):
    r = requests.post(f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/{method}", timeout=120, **kw)
    data = r.json() if r.content else {}
    if not data.get("ok"):
        raise RuntimeError(f"Telegram refused {method}: {data.get('description', r.status_code)}")
    return data["result"]


def send_text(text, chat_id=None):
    return _api("sendMessage", data={"chat_id": chat_id or config.TELEGRAM_CHAT_ID, "text": text})


def send_for_approval(video_path, caption, post_id):
    buttons = {"inline_keyboard": [[
        {"text": "✅ Post", "callback_data": f"approve:{post_id}"},
        {"text": "🔄 New design", "callback_data": f"redesign:{post_id}"},
        {"text": "❌ Skip", "callback_data": f"skip:{post_id}"},
    ]]}
    with open(video_path, "rb") as f:
        msg = _api("sendVideo", data={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "caption": caption[:1024],
            "supports_streaming": "true",
            "reply_markup": json.dumps(buttons),
        }, files={"video": f})
    return msg["message_id"]


def get_updates(offset):
    return _api("getUpdates", data={"offset": offset, "timeout": 0,
                                    "allowed_updates": json.dumps(["message", "callback_query"])})


def answer(callback_id, text):
    _api("answerCallbackQuery", data={"callback_query_id": callback_id, "text": text})


def clear_buttons(message_id, note):
    """Removes the buttons and adds a status line, so the choice can't be made twice."""
    _api("editMessageReplyMarkup", data={"chat_id": config.TELEGRAM_CHAT_ID, "message_id": message_id,
                                         "reply_markup": json.dumps({"inline_keyboard": []})})
    send_text(note)
