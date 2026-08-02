import json
import os
import time
import urllib.request
import urllib.error

BOT_TOKEN = os.environ.get("MUSIC_BOT_TOKEN")
CHANNEL_ID = os.environ.get("MUSIC_CHANNEL_ID")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

def _post(method, payload, timeout=15, max_retries=4):
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(f"{API_BASE}/{method}", data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 429:
                try:
                    retry_after = json.loads(body).get("parameters", {}).get("retry_after", 5)
                except Exception:
                    retry_after = 5
                time.sleep(retry_after + 1)
                continue
            return {"ok": False, "error_code": e.code, "description": body}
        except Exception:
            time.sleep(2)
    return {"ok": False, "description": f"gave up after {max_retries} retries"}

def get_updates(offset=None, timeout=5):
    if not BOT_TOKEN:
        return []
    url = f"{API_BASE}/getUpdates?timeout={timeout}"
    if offset:
        url += f"&offset={offset}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
            return json.loads(resp.read().decode("utf-8")).get("result", [])
    except Exception:
        return []

def edit_message_caption(message_id, caption, parse_mode="HTML"):
    payload = {
        "chat_id": CHANNEL_ID,
        "message_id": message_id,
        "caption": caption,
        "parse_mode": parse_mode,
    }
    return _post("editMessageCaption", payload)

def send_message(text, reply_to_message_id=None, parse_mode="HTML"):
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    return _post("sendMessage", payload)

def pin_chat_message(message_id):
    payload = {
        "chat_id": CHANNEL_ID,
        "message_id": message_id,
        "disable_notification": True
    }
    return _post("pinChatMessage", payload)

def iter_channel_audio_posts(updates):
    for update in updates:
        post = update.get("channel_post")
        if not post:
            continue
        chat_id = post.get("chat", {}).get("id")
        if CHANNEL_ID and str(chat_id) != str(CHANNEL_ID) and not str(CHANNEL_ID).startswith("@"):
            continue
        audio = post.get("audio")
        if not audio:
            continue
        yield post.get("message_id"), audio