import base64
import json
import os
import time
import urllib.request
import urllib.error
import urllib.parse

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"


def get_access_token():
    """Client Credentials flow. Token is valid ~1 hour; this script's
    whole run is a few minutes, so we just fetch one token per run
    instead of persisting/refreshing it."""
    if not CLIENT_ID or not CLIENT_SECRET:
        print("[spotify] SPOTIFY_CLIENT_ID/SECRET not set.")
        return None

    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8")).get("access_token")
    except Exception as e:
        print(f"[spotify] failed to get access token: {e}")
        return None


def _get(token, path, params, max_retries=3):
    url = f"{API_BASE}{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry_after = int(e.headers.get("Retry-After", "5"))
                print(f"[spotify] rate limited, waiting {retry_after}s (attempt {attempt}/{max_retries})")
                time.sleep(retry_after + 1)
                continue
            print(f"[spotify] API error {e.code} for {path}")
            return None
        except Exception as e:
            print(f"[spotify] request failed: {e}")
            return None
    return None


def search_track(token, performer, title):
    """Best-effort search. Returns None on no match instead of raising —
    caller should fall back to the raw Telegram tags when this happens."""
    if not token or not title:
        return None

    query = f"track:{title}"
    if performer:
        query += f" artist:{performer}"

    result = _get(token, "/search", {"q": query, "type": "track", "limit": 1})
    if not result:
        return None

    items = result.get("tracks", {}).get("items", [])
    if not items:
        return None

    track = items[0]
    return {
        "name": track.get("name"),
        "artists": [a.get("name") for a in track.get("artists", [])],
        "artist_ids": [a.get("id") for a in track.get("artists", [])],
        "album": track.get("album", {}).get("name"),
        "release_date": track.get("album", {}).get("release_date"),
    }


def get_artist_genres(token, artist_id):
    """Genres are NOT on the track object — Spotify only exposes them on
    the artist object, so this is a required second call."""
    if not token or not artist_id:
        return []

    result = _get(token, f"/artists/{artist_id}", {})
    if not result:
        return []
    return result.get("genres", [])
