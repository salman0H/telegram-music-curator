"""Resolve recordings with MusicBrainz and fetch similar tracks from Last.fm."""
import json
import os
import re
import time
import urllib.parse
import urllib.request
import urllib.error

_LAST_MB_REQUEST = 0.0
USER_AGENT = "TelegramMusicCurator/1.0 (https://github.com/salman0H/telegram-music-curator)"


def _get_json(url):
    global _LAST_MB_REQUEST
    provider = "MusicBrainz" if urllib.parse.urlsplit(url).hostname == "musicbrainz.org" else "Last.fm"
    for attempt in range(3):
        if provider == "MusicBrainz":
            time.sleep(max(0, 1.1 - (time.monotonic() - _LAST_MB_REQUEST)))
            _LAST_MB_REQUEST = time.monotonic()
        retry_after = None
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.load(response)
            if not isinstance(data, dict):
                raise ValueError("invalid response shape")
            code = data.get("error")
            if not code:
                return data
            reason = f"API error {code}"
            retryable = code in (8, 11, 16, 29)
            if not retryable:
                print(f"[recommendations] {provider}: {reason}; not retrying")
                return data
        except urllib.error.HTTPError as exc:
            reason = f"HTTP {exc.code}"
            retryable = exc.code in (429, 500, 502, 503, 504)
            header = exc.headers.get("Retry-After") if exc.headers else None
            exc.close()
            if header and header.isdigit():
                retry_after = min(int(header), 60)
        except (OSError, ValueError) as exc:
            # Exception strings and URLs can contain the key; log only the type.
            reason = type(exc).__name__
            retryable = True
        if retryable and attempt < 2:
            delay = retry_after if retry_after is not None else 2 ** (attempt + 1)
            print(f"[recommendations] {provider}: {reason}; retry {attempt + 1}/2 in {delay}s")
            time.sleep(delay)
        else:
            print(f"[recommendations] {provider}: {reason}; request failed after {attempt + 1} attempt(s)")
            return {}
    return {}


def _normalize(value):
    return " ".join(value.casefold().split())


def _resolve_recording(artist, title):
    def quoted(value):
        return '"' + re.sub(r'([\\"])', r'\\\1', value) + '"'
    query = f"recording:{quoted(title)} AND artist:{quoted(artist)}"
    params = urllib.parse.urlencode({"query": query, "fmt": "json", "limit": 3})
    data = _get_json("https://musicbrainz.org/ws/2/recording/?" + params)
    for recording in data.get("recordings", []):
        credits = recording.get("artist-credit", [])
        names = [c.get("artist", {}).get("name", "") for c in credits if isinstance(c, dict)]
        if (_normalize(recording.get("title", "")) == _normalize(title)
                and any(_normalize(name) == _normalize(artist) for name in names)):
            return recording.get("id")
    return None


def recommend_tracks(artist, title, limit=3):
    """Return artist — title labels; missing credentials or matches never block curation."""
    if limit <= 0:
        return []
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
    def fetch_tracks(parameters):
        data = _get_json("https://ws.audioscrobbler.com/2.0/?" + urllib.parse.urlencode(parameters))
        similar = data.get("similartracks", {})
        tracks = similar.get("track", []) if isinstance(similar, dict) else []
        if isinstance(tracks, dict):
            tracks = [tracks]
        return tracks if isinstance(tracks, list) else []

    tracks = fetch_tracks(params)
    if mbid and not tracks:
        print("[recommendations] Last.fm: no MBID results; trying artist/title")
        params.pop("mbid")
        params.update(artist=artist, track=title)
        tracks = fetch_tracks(params)
    titles = []
    seen = {(_normalize(artist), _normalize(title))}
    for track in tracks:
        name = track.get("name") if isinstance(track, dict) else None
        credit = track.get("artist", {}) if isinstance(track, dict) else {}
        performer = credit.get("name") if isinstance(credit, dict) else credit
        if not isinstance(name, str) or not isinstance(performer, str):
            continue
        name = " ".join(name.split())
        performer = " ".join(performer.split())
        identity = (_normalize(performer), _normalize(name))
        if not name or not performer or identity in seen or len(name) > 150 or len(performer) > 150:
            continue
        seen.add(identity)
        titles.append(f"{performer} — {name}")
        if len(titles) >= limit:
            break
    print(f"[recommendations] {artist} — {title}: {len(titles)} suggested title(s)")
    return titles
