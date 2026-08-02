import json
import urllib.request
import urllib.error
import urllib.parse
import time

def search_track(performer, title):
    if not title:
        return None
    
    query = title
    if performer and performer.lower() != "unknown artist":
        query = f"{performer} {title}"
        
    params = urllib.parse.urlencode({"term": query, "entity": "song", "limit": 1})
    url = f"https://itunes.apple.com/search?{params}"
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("resultCount", 0) > 0:
                    track = data["results"][0]
                    return {
                        "name": track.get("trackName"),
                        "artists": [track.get("artistName")] if track.get("artistName") else [],
                        "album": track.get("collectionName"),
                        "release_date": track.get("releaseDate"),
                        "genres": [track.get("primaryGenreName")] if track.get("primaryGenreName") else []
                    }
                return None
        except Exception:
            time.sleep(2)
    return None