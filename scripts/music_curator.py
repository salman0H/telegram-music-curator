import argparse
import re
import sys

import state
import telegram_client
import itunes_client
import caption_formatter
import hashtag_index
import recommendations

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()

def get_message_link(channel_id, message_id):
    cid_str = str(channel_id)
    if cid_str.startswith("-100"):
        return f"https://t.me/c/{cid_str[4:]}/{message_id}"
    elif cid_str.startswith("@"):
        return f"https://t.me/{cid_str[1:]}/{message_id}"
    return f"https://t.me/c/{cid_str}/{message_id}"

def extract_performer_title(audio):
    performer = audio.get("performer")
    title = audio.get("title")
    if performer and title:
        return performer, title

    file_name = audio.get("file_name", "")
    name_no_ext = re.sub(r"\.\w{2,4}$", "", file_name)
    match = re.match(r"^\s*(.+?)\s*-\s*(.+?)\s*$", name_no_ext)
    if match:
        return performer or match.group(1), title or match.group(2)
    return performer or "Unknown Artist", title or (name_no_ext or "Unknown Title")

def process_track(channel_id, message_id, audio, dry_run):
    performer, title = extract_performer_title(audio)
    album = None
    year = None
    genres = []

    match = itunes_client.search_track(performer, title)
    if match:
        performer = match["artists"][0] if match["artists"] else performer
        title = match["name"] or title
        album = match.get("album")
        release_date = match.get("release_date")
        if release_date:
            year = release_date[:4]
        if match.get("genres"):
            genres = match["genres"]

    hashtags = caption_formatter.genres_to_hashtags(genres)
    suggestions = recommendations.recommend_tracks(performer, title)
    caption = caption_formatter.build_caption(performer, title, album, year, genres, suggestions)

    if dry_run:
        return True, performer, title, hashtags

    result = telegram_client.edit_message_caption(message_id, caption)
    
    if not result or not result.get("ok"):
        reply_result = telegram_client.send_message(caption, reply_to_message_id=message_id)
        if not reply_result or not reply_result.get("ok"):
            link = get_message_link(channel_id, message_id)
            fallback_caption = f"🔗 <a href='{link}'><b>Original Track</b></a>\n\n{caption}"
            final_result = telegram_client.send_message(fallback_caption)
            if not final_result or not final_result.get("ok"):
                return False, None, None, []

    return True, performer, title, hashtags

def escape_html(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def build_summary_messages(items, bulk=False, limit=4000):
    header = (f"📦 <b>Bulk Upload Summary ({len(items)} tracks)</b>\n" if bulk
              else f"📊 <b>Curator Summary ({len(items)} tracks categorized)</b>\n")
    messages = []
    current = header
    for message_id, name in items:
        link = get_message_link(telegram_client.CHANNEL_ID, message_id)
        # Bound a single label before escaping, keeping HTML tags intact.
        label = escape_html(name[:500])
        line = f"▪️ <a href='{link}'>{label}</a>"
        if len(current) + len(line) + 1 > limit:
            messages.append(current)
            current = header
        current += "\n" + line
    if items:
        messages.append(current)
    return messages


def send_summaries(items, bulk=False):
    for text in build_summary_messages(items, bulk=bulk):
        response = telegram_client.send_message(text)
        if not response or not response.get("ok"):
            return False
        message_id = response.get("result", {}).get("message_id")
        if message_id:
            telegram_client.pin_chat_message(message_id)
    return True


def main():
    args = parse_args()
    if not telegram_client.CHANNEL_ID:
        print("Error: MUSIC_CHANNEL_ID is not set in environment variables.")
        sys.exit(1)

    st = state.load_state()
    updates = list(st.get("pending_updates", []))
    next_offset = st.get("offset")
    # Telegram returns at most 100 updates per page. Keep a durable queue
    # before acknowledging each page, so larger uploads can be counted safely.
    while True:
        page = telegram_client.get_updates(offset=next_offset)
        if not page:
            break
        known_ids = {update.get("update_id") for update in updates}
        updates.extend(update for update in page if update.get("update_id") not in known_ids)
        next_offset = max(update["update_id"] for update in page) + 1
        if not args.dry_run:
            st["pending_updates"] = updates
            st["offset"] = next_offset
            state.save_state(st)
        if len(page) < 100:
            break

    if not updates:
        print("No new updates found from Telegram.")
        return

    processed_items = []
    failure_count = 0
    index = hashtag_index.load_index()

    # Extract all unprocessed audio posts
    new_audio_posts = []
    for message_id, audio in telegram_client.iter_channel_audio_posts(updates):
        if not state.is_processed(st, message_id):
            new_audio_posts.append((message_id, audio))
        else:
            print(f"Message ID {message_id} was already processed previously, skipping.")

    audio_count = len(new_audio_posts)

    if audio_count > 100:
        print(f"Bulk upload detected: {audio_count} tracks. Sending links only.")
        for message_id, audio in new_audio_posts:
            performer, title = extract_performer_title(audio)
            processed_items.append((message_id, f"{performer} - {title}"))
        if not args.dry_run and send_summaries(processed_items, bulk=True):
            for message_id, _ in processed_items:
                state.mark_processed(st, message_id)
    else:
        for message_id, audio in new_audio_posts:
            print(f"Processing new audio message ID: {message_id}")
            ok, performer, title, hashtags = process_track(
                telegram_client.CHANNEL_ID, message_id, audio, args.dry_run)
            if ok:
                state.mark_processed(st, message_id)
                processed_items.append((message_id, f"{performer} - {title}"))
                link = get_message_link(telegram_client.CHANNEL_ID, message_id)
                for tag in hashtags:
                    hashtag_index.add_entry(index, tag, message_id, link, performer, title)
                if not args.dry_run:
                    # Preserve progress throughout long batches.
                    hashtag_index.save_index(index)
                    hashtag_index.write_summary(index)
                    state.save_state(st)
            else:
                failure_count += 1
        if processed_items and not args.dry_run:
            send_summaries(processed_items)

    st["offset"] = next_offset
    st["consecutive_failures"] = 0 if processed_items or failure_count == 0 else st.get("consecutive_failures", 0) + 1

    if not args.dry_run:
        completed_ids = set(st.get("processed_ids", []))
        st["pending_updates"] = [
            update for update in updates
            if any(message_id not in completed_ids
                   for message_id, _ in telegram_client.iter_channel_audio_posts([update]))
        ]
        state.save_state(st)
        if processed_items and audio_count <= 100:
            hashtag_index.save_index(index)
            hashtag_index.write_summary(index)

    if not processed_items:
        if audio_count == 0:
            print("\nSummary: No audio tracks were found in the fetched updates.")
        else:
            print(f"\nSummary: {audio_count} audio track(s) found, but none were newly processed (either failed or already processed).")

if __name__ == "__main__":
    main()
