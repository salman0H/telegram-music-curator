import argparse
import re
import sys
import time

import state
import telegram_client
import itunes_client
import caption_formatter

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()

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

def process_track(message_id, audio, dry_run):
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

    caption = caption_formatter.build_caption(performer, title, album, year, genres)
    track_display = f"{performer} - {title}"

    if dry_run:
        return True, track_display

    result = telegram_client.edit_message_caption(message_id, caption)
    
    if not result or not result.get("ok"):
        reply_result = telegram_client.send_message(caption, reply_to_message_id=message_id)
        if not reply_result or not reply_result.get("ok"):
            return False, None

    return True, track_display

def get_message_link(channel_id, message_id):
    cid_str = str(channel_id)
    if cid_str.startswith("-100"):
        return f"https://t.me/c/{cid_str[4:]}/{message_id}"
    elif cid_str.startswith("@"):
        return f"https://t.me/{cid_str[1:]}/{message_id}"
    return f"https://t.me/c/{cid_str}/{message_id}"

def escape_html(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def main():
    start_time = time.time()
    TIME_LIMIT = 240
    
    args = parse_args()
    if not telegram_client.CHANNEL_ID:
        sys.exit(1)

    st = state.load_state()
    updates = telegram_client.get_updates(offset=st.get("offset"))
    if not updates:
        return

    processed_items = []
    failure_count = 0
    next_offset = st.get("offset")

    for update in updates:
        next_offset = update.get("update_id", 0) + 1

    for message_id, audio in telegram_client.iter_channel_audio_posts(updates):
        if time.time() - start_time > TIME_LIMIT:
            break
            
        if state.is_processed(st, message_id):
            continue
            
        ok, track_name = process_track(message_id, audio, args.dry_run)
        if ok:
            state.mark_processed(st, message_id)
            if track_name:
                processed_items.append((message_id, track_name))
        else:
            failure_count += 1

    st["offset"] = next_offset
    st["consecutive_failures"] = 0 if processed_items or failure_count == 0 else st.get("consecutive_failures", 0) + 1

    if not args.dry_run:
        state.save_state(st)

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

if __name__ == "__main__":
    main()