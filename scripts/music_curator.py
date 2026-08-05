import argparse
import re
import sys
import time

import state
import telegram_client
import itunes_client
import caption_formatter
import hashtag_index

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
    caption = caption_formatter.build_caption(performer, title, album, year, genres)

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

def main():
    start_time = time.time()
    TIME_LIMIT = 240
    
    args = parse_args()
    if not telegram_client.CHANNEL_ID:
        print("Error: MUSIC_CHANNEL_ID is not set in environment variables.")
        sys.exit(1)

    print(f"Starting curator for channel ID: {telegram_client.CHANNEL_ID}")

    st = state.load_state()
    print(f"Current offset from state: {st.get('offset')}")
    
    updates = telegram_client.get_updates(offset=st.get("offset"))
    if not updates:
        print("No new updates found from Telegram.")
        return

    print(f"Fetched {len(updates)} new update(s) from Telegram.")

    processed_items = []
    failure_count = 0
    next_offset = st.get("offset")
    
    index = hashtag_index.load_index()

    for update in updates:
        update_id = update.get("update_id", 0)
        if update_id >= next_offset:
            next_offset = update_id + 1

    # Extract all unprocessed audio posts
    new_audio_posts = []
    for message_id, audio in telegram_client.iter_channel_audio_posts(updates):
        if not state.is_processed(st, message_id):
            new_audio_posts.append((message_id, audio))
        else:
            print(f"Message ID {message_id} was already processed previously, skipping.")

    audio_count = len(new_audio_posts)

    if audio_count > 20:
        print(f"Bulk upload detected: {audio_count} tracks. Skipping individual tags and replies.")
        summary_lines = [f"📦 <b>Bulk Upload Summary ({audio_count} tracks)</b>\n"]
        
        for message_id, audio in new_audio_posts:
            performer, title = extract_performer_title(audio)
            track_name = f"{performer} - {title}"
            safe_name = escape_html(track_name)
            link = get_message_link(telegram_client.CHANNEL_ID, message_id)
            
            summary_lines.append(f"▪️ <a href='{link}'>{safe_name}</a>")
            processed_items.append((message_id, track_name))
            
            if not args.dry_run:
                state.mark_processed(st, message_id)
                
        if not args.dry_run:
            summary_text = "\n".join(summary_lines)
            if len(summary_text) > 4000:
                summary_text = summary_text[:4000] + "\n\n... [Truncated]"
                
            msg_response = telegram_client.send_message(summary_text)
            if msg_response and msg_response.get("ok"):
                sent_message_id = msg_response.get("result", {}).get("message_id")
                if sent_message_id:
                    telegram_client.pin_chat_message(sent_message_id)
                    print("Bulk summary message sent and pinned.")
    else:
        for message_id, audio in new_audio_posts:
            if time.time() - start_time > TIME_LIMIT:
                print("Time limit reached, stopping early.")
                break
                
            print(f"Processing new audio message ID: {message_id}")
            ok, performer, title, hashtags = process_track(telegram_client.CHANNEL_ID, message_id, audio, args.dry_run)
            
            if ok:
                state.mark_processed(st, message_id)
                track_name = f"{performer} - {title}"
                processed_items.append((message_id, track_name))
                print(f" -> Success: {track_name}")
                
                link = get_message_link(telegram_client.CHANNEL_ID, message_id)
                for tag in hashtags:
                    hashtag_index.add_entry(index, tag, message_id, link, performer, title)
            else:
                print(f" -> Failed to process message ID: {message_id}")
                failure_count += 1

        if processed_items and not args.dry_run:
            summary_lines = [f"📊 <b>Curator Summary</b>\n\n✅ <b>{len(processed_items)}</b> tracks categorized:\n"]
            for msg_id, t_name in processed_items:
                link = get_message_link(telegram_client.CHANNEL_ID, msg_id)
                safe_name = escape_html(t_name)
                summary_lines.append(f"▪️ <a href='{link}'>{safe_name}</a>")
            
            summary_text = "\n".join(summary_lines)
            if len(summary_text) > 4000:
                summary_text = summary_text[:4000] + "\n\n... [Truncated]"
                
            msg_response = telegram_client.send_message(summary_text)
            if msg_response and msg_response.get("ok"):
                sent_message_id = msg_response.get("result", {}).get("message_id")
                if sent_message_id:
                    telegram_client.pin_chat_message(sent_message_id)
                    print("Summary message sent and pinned in the channel.")

    st["offset"] = next_offset
    st["consecutive_failures"] = 0 if processed_items or failure_count == 0 else st.get("consecutive_failures", 0) + 1

    if not args.dry_run:
        state.save_state(st)
        if processed_items and audio_count <= 20:
            hashtag_index.save_index(index)
            hashtag_index.write_summary(index)

    if not processed_items:
        if audio_count == 0:
            print("\nSummary: No audio tracks were found in the fetched updates.")
        else:
            print(f"\nSummary: {audio_count} audio track(s) found, but none were newly processed (either failed or already processed).")

if __name__ == "__main__":
    main()
