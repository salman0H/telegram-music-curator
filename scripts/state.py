import json
import os

STATE_FILE = "music_state.json"

# Cap how many processed message_ids we remember. Without this the file
# would grow forever; with it, we just accept that a message older than
# MAX_PROCESSED_IDS entries ago could theoretically be reprocessed if it
# somehow reappeared in getUpdates (extremely unlikely in practice, since
# Telegram's own update retention window is much shorter than this cap).
MAX_PROCESSED_IDS = 2000

DEFAULT_STATE = {
    "offset": None,
    "processed_ids": [],
    "consecutive_failures": 0,
}


def load_state():
    if not os.path.exists(STATE_FILE):
        return dict(DEFAULT_STATE)
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[state] failed to read {STATE_FILE}, starting fresh: {e}")
        return dict(DEFAULT_STATE)

    # Merge with defaults so a state file written by an older version of
    # this script (missing a newer key) doesn't crash the current one.
    merged = dict(DEFAULT_STATE)
    merged.update(data)
    return merged


def save_state(state):
    # Trim processed_ids before writing, keeping the most recent ones.
    if len(state.get("processed_ids", [])) > MAX_PROCESSED_IDS:
        state["processed_ids"] = state["processed_ids"][-MAX_PROCESSED_IDS:]

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def is_processed(state, message_id):
    return message_id in state.get("processed_ids", [])


def mark_processed(state, message_id):
    state.setdefault("processed_ids", []).append(message_id)
