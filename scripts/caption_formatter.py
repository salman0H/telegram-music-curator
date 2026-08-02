import json
import os
import re

CAPTION_CHAR_LIMIT = 1024  # Telegram caption limit is 1024, NOT the 4096
                            # used for regular text messages.

_MAP_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "genre_hashtags.json")
MAX_HASHTAGS = 3


def _load_genre_map():
    try:
        with open(_MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[caption] failed to load genre map: {e}")
        return {}


_GENRE_MAP = _load_genre_map()


def _slugify_fallback(genre):
    # Turn an unmapped raw genre like "vapor twitch" into "#VaporTwitch".
    words = re.split(r"[\s\-]+", genre.strip())
    return "#" + "".join(w.capitalize() for w in words if w)


def genres_to_hashtags(genres):
    tags = []
    for g in genres:
        g_lower = g.lower().strip()
        tag = _GENRE_MAP.get(g_lower) or _slugify_fallback(g_lower)
        if tag not in tags:
            tags.append(tag)
        if len(tags) >= MAX_HASHTAGS:
            break
    return tags


def _escape_html(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_caption(performer, title, album=None, year=None, genres=None):
    performer = _escape_html(performer or "Unknown Artist")
    title = _escape_html(title or "Unknown Title")

    lines = [f"<blockquote>🎙 <b>{performer}</b>\n🎵 {title}</blockquote>"]

    meta_bits = []
    if album:
        meta_bits.append(f"💿 {_escape_html(album)}")
    if year:
        meta_bits.append(f"📅 {year}")
    if meta_bits:
        lines.append(" | ".join(meta_bits))

    hashtags = genres_to_hashtags(genres or [])
    if hashtags:
        lines.append(" ".join(hashtags))

    caption = "\n\n".join(lines)

    # Hard safety cap — should rarely trigger given the compact format
    # above, but a very long album/title combo could still exceed it.
    if len(caption) > CAPTION_CHAR_LIMIT:
        caption = caption[: CAPTION_CHAR_LIMIT - 1] + "…"

    return caption
