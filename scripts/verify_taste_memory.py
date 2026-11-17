"""Verify authenticated journal persistence without logging personal contents."""
import os
from pathlib import Path
import secrets
import tempfile
from taste_memory import read_store, write_store

def main():
    password = os.environ.get("TASTE_MEMORY_PASSWORD")
    if not password:
        raise RuntimeError("TASTE_MEMORY_PASSWORD missing: encrypted recording is disabled")
    path = Path(os.environ.get("TASTE_MEMORY_FILE", "data/taste_memory.enc"))
    # Isolated synthetic probe never enters the production journal.
    with tempfile.TemporaryDirectory() as directory:
        probe = Path(directory) / "probe.enc"
        marker = secrets.token_hex(24)
        expected = {"schema_version": 1, "events": {}, "probe": marker}
        write_store(probe, password, expected)
        assert marker.encode() not in probe.read_bytes()
        assert read_store(probe, password) == expected
    print("[taste_memory] encryption/decryption probe PASS (isolated temporary file)")
    if not path.exists():
        print("[taste_memory] production journal ABSENT; no recorded choices yet")
        return
    store = read_store(path, password)
    events = list(store["events"].values())
    admin = sum("vibe_admin" in event["sources"] for event in events)
    timed = sum(event["sent_at_utc"] is not None for event in events)
    print(f"[taste_memory] authenticated journal PASS: events={len(events)}, admin_choices={admin}, timestamped={timed}")

if __name__ == "__main__":
    main()
