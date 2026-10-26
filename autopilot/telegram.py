"""Approval by Telegram: you get each draft on your phone with Approve / Skip buttons."""

import os
from pathlib import Path

import requests

API = "https://api.telegram.org/bot{token}/{method}"


def _call(method, **kwargs):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    resp = requests.post(API.format(token=token, method=method), timeout=60, **kwargs)
    resp.raise_for_status()
    return resp.json()["result"]


def send_draft(post_id, image_path, captions, problems):
    chat = os.environ["TELEGRAM_CHAT_ID"]
    with open(image_path, "rb") as f:
        _call("sendPhoto", data={"chat_id": chat, "caption": f"Draft for {post_id}"}, files={"photo": f})
    text = f"FACEBOOK / INSTAGRAM\n\n{captions['long']}\n\n---\nX / TIKTOK\n\n{captions['short']}"
    if problems:
        text += "\n\n⚠️ Compliance flags:\n" + "\n".join(f"- {p}" for p in problems)
    buttons = {"inline_keyboard": [[
        {"text": "✅ Approve", "callback_data": f"approve:{post_id}"},
        {"text": "⏭ Skip", "callback_data": f"skip:{post_id}"},
    ]]}
    _call("sendMessage", json={"chat_id": chat, "text": text[:4000], "reply_markup": buttons})


def get_decision(post_id):
    """Return 'approve', 'skip' or None. Only button presses from your own chat count."""
    chat = str(os.environ["TELEGRAM_CHAT_ID"])
    decision = None
    for update in _call("getUpdates", json={"allowed_updates": ["callback_query"]}):
        cq = update.get("callback_query")
        if not cq or str(cq["message"]["chat"]["id"]) != chat:
            continue
        action, _, pid = cq.get("data", "").partition(":")
        if pid == post_id and action in ("approve", "skip"):
            decision = action  # latest press wins
            try:
                _call("answerCallbackQuery", json={"callback_query_id": cq["id"], "text": f"{action}d"})
            except requests.HTTPError:
                pass  # old presses can't be answered; harmless
    return decision


def send_document(path, caption):
    with open(path, "rb") as f:
        _call("sendDocument", data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "caption": caption[:1000]},
              files={"document": f})


def notify(text):
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        _call("sendMessage", json={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text})


def send_text(text, reply_to=None):
    """Send a message to your chat and return its message_id."""
    body = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text[:4000]}
    if reply_to:
        body["reply_to_message_id"] = reply_to
    return _call("sendMessage", json=body)["message_id"]


def get_messages(offset):
    """New messages from your own chat since `offset`. Returns (messages, next_offset)."""
    chat = str(os.environ["TELEGRAM_CHAT_ID"])
    updates = _call("getUpdates", json={"offset": offset, "allowed_updates": ["message"], "timeout": 0})
    msgs, nxt = [], offset
    for u in updates:
        nxt = max(nxt, u["update_id"] + 1)
        m = u.get("message")
        if m and str(m["chat"]["id"]) == chat:
            msgs.append(m)
    return msgs, nxt


def download(file_id, dest):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    path = _call("getFile", json={"file_id": file_id})["file_path"]
    r = requests.get(f"https://api.telegram.org/file/bot{token}/{path}", timeout=120)
    r.raise_for_status()
    Path(dest).write_bytes(r.content)
    return Path(dest)
