import argparse
import re
import sys

import state
import telegram_client
import spotify_client
import caption_formatter


def parse_args():
    parser = argparse.ArgumentParser(description="Enrich channel audio captions via Spotify metadata.")
    parser.add_argument("--dry-run", action="store_true", help="Build captions and print them, but do not call editMessageCaption.")
    return parser.parse_args()


def extract_performer_title(audio, message_id):
    """audio.performer/title are only set if the uploader tagged the file.
    Fall back to parsing 'Artist - Title' style filenames when missing."""
    performer = audio.get("performer")
    title = audio.get("title")
    if performer and title:
        return performer, title

    file_name = audio.get("file_name", "")
    name_no_ext = re.sub(r"\.\w{2,4}$", "", file_name)
    match = re.match(r"^\s*(.+?)\s*-\s*(.+?)\s*$", name_no_ext)
    if match:
        return performer or match.group(1), title or match.group(2)

    print(f"[curator] message {message_id}: no usable tags or filename pattern, using raw fallback")
    return performer or "Unknown Artist", title or (name_no_ext or "Unknown Title")


def process_track(message_id, audio, token, dry_run):
    performer, title = extract_performer_title(audio, message_id)

    album = None
    year = None
    genres = []

    match = spotify_client.search_track(token, performer, title)
    if match:
        performer = match["artists"][0] if match["artists"] else performer
        title = match["name"] or title
        album = match.get("album")
        release_date = match.get("release_date")
        if release_date:
            year = release_date[:4]
        if match.get("artist_ids"):
            genres = spotify_client.get_artist_genres(token, match["artist_ids"][0])
    else:
        print(f"[curator] message {message_id}: no Spotify match, using raw Telegram tags only")

    caption = caption_formatter.build_caption(performer, title, album, year, genres)

    if dry_run:
        print(f"--- message {message_id} (dry-run) ---\n{caption}\n")
        return True

    result = telegram_client.edit_message_caption(message_id, caption)
    if not result or not result.get("ok"):
        print(f"[curator] message {message_id}: caption edit failed: {result}")
        return False
    return True


def main():
    args = parse_args()

    if not telegram_client.CHANNEL_ID:
        print("[curator] MUSIC_CHANNEL_ID is not set, aborting.")
        sys.exit(1)

    st = state.load_state()
    updates = telegram_client.get_updates(offset=st.get("offset"))

    if not updates:
        print("[curator] no new updates.")
        return

    token = None if args.dry_run else spotify_client.get_access_token()
    if not args.dry_run and not token:
        print("[curator] could not obtain Spotify token, aborting this run.")
        st["consecutive_failures"] = st.get("consecutive_failures", 0) + 1
        state.save_state(st)
        sys.exit(1)

    processed_count = 0
    failure_count = 0
    next_offset = st.get("offset")

    for update in updates:
        next_offset = update.get("update_id", 0) + 1

    for message_id, audio in telegram_client.iter_channel_audio_posts(updates):
        if state.is_processed(st, message_id):
            continue
        ok = process_track(message_id, audio, token, args.dry_run)
        if ok:
            state.mark_processed(st, message_id)
            processed_count += 1
        else:
            failure_count += 1

    st["offset"] = next_offset
    st["consecutive_failures"] = 0 if processed_count > 0 or failure_count == 0 else st.get("consecutive_failures", 0) + 1

    if not args.dry_run:
        state.save_state(st)

    print(f"[curator] done. processed={processed_count} failed={failure_count}")


if __name__ == "__main__":
    main()
