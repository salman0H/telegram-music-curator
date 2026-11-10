"""Resolve recordings with MusicBrainz and fetch similar tracks from Last.fm."""
import json
import os
import re
import time
import urllib.parse
import urllib.request

_LAST_MB_REQUEST = 0.0
USER_AGENT = "TelegramMusicCurator/1.0 (https://github.com/salman0H/telegram-music-curator)"


def _get_json(url):
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.load(response)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        # Do not log URLs: Last.fm requests contain an API key.
        print("[recommendations] provider unavailable; continuing without its results")
        return {}


def _normalize(value):
    return " ".join(value.casefold().split())


def _resolve_recording(artist, title):
    global _LAST_MB_REQUEST
    # MusicBrainz allows at most one request per second per application.
    time.sleep(max(0, 1.1 - (time.monotonic() - _LAST_MB_REQUEST)))
    def quoted(value):
        return '"' + re.sub(r'([\\"])', r'\\\1', value) + '"'
    query = f"recording:{quoted(title)} AND artist:{quoted(artist)}"
    params = urllib.parse.urlencode({"query": query, "fmt": "json", "limit": 3})
    _LAST_MB_REQUEST = time.monotonic()
    data = _get_json("https://musicbrainz.org/ws/2/recording/?" + params)
    for recording in data.get("recordings", []):
        credits = recording.get("artist-credit", [])
        names = [c.get("artist", {}).get("name", "") for c in credits if isinstance(c, dict)]
        if (_normalize(recording.get("title", "")) == _normalize(title)
                and any(_normalize(name) == _normalize(artist) for name in names)):
            return recording.get("id")
    return None


def recommend_tracks(artist, title, limit=3):
    """Return titles only; missing credentials or matches never block curation."""
    api_key = os.environ.get("LASTFM_API_KEY")
    if not api_key or not title or artist == "Unknown Artist":
        return []
    mbid = _resolve_recording(artist, title)
    params = {"method": "track.getSimilar", "api_key": api_key,
              "format": "json", "limit": 10, "autocorrect": 1}
    if mbid:
        params["mbid"] = mbid
    else:
        params.update(artist=artist, track=title)
    data = _get_json("https://ws.audioscrobbler.com/2.0/?" + urllib.parse.urlencode(params))
    similar = data.get("similartracks", {})
    tracks = similar.get("track", []) if isinstance(similar, dict) else []
    if isinstance(tracks, dict):
        tracks = [tracks]
    titles = []
    seen = {_normalize(title)}
    for track in tracks:
        name = track.get("name") if isinstance(track, dict) else None
        if not isinstance(name, str):
            continue
        name = " ".join(name.split())
        normalized = _normalize(name)
        if not name or normalized in seen or len(name) > 150:
            continue
        seen.add(normalized)
        titles.append(name)
        if len(titles) >= limit:
            break
    return titles
