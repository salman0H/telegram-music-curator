import json
import os

INDEX_FILE = "hashtag_index.json"
SUMMARY_FILE = "hashtag_summary.txt"


def load_index():
    if not os.path.exists(INDEX_FILE):
        return {}
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[hashtag_index] failed to load {INDEX_FILE}, starting fresh: {e}")
        return {}


def save_index(index):
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def add_entry(index, hashtag, message_id, link, performer, title):
    entries = index.setdefault(hashtag, [])
    entries.append({
        "message_id": message_id,
        "link": link,
        "performer": performer,
        "title": title,
    })


def write_summary(index):
    """Just counts, sorted descending — the per-song list lives in
    INDEX_FILE / is browsable natively in Telegram by tapping a hashtag.
    This file is for a quick 'what genres do I even have, and how many
    songs in each' overview."""
    counts = sorted(((tag, len(entries)) for tag, entries in index.items()), key=lambda x: -x[1])
    lines = [f"{tag}: {count}" for tag, count in counts]
    total = sum(c for _, c in counts)
    header = f"Hashtag summary — {len(counts)} tags, {total} tagged songs\n" + "=" * 40 + "\n"
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines) + "\n")
    return counts