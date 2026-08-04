# 🦇 Poetic Vibe Curator 🎼✨

> Your serverless, AI-powered midnight poet for Telegram.

Welcome to the **Poetic Vibe Curator**! This isn't just a bot; it's a digital philosopher that lives in your public Telegram channel. It silently listens to the tracks you drop during the day, and right at the stroke of midnight, it wakes up, analyzes the vibes, and elegantly edits your captions with soul-crushing, melancholic poetry. 🍷🍂

## ✨ What Makes It Cool?

* 🥷 **The Silent Observer:** Checks your channel every few hours without making a sound. No annoying replies, no spam.
* 🧠 **Midnight Epiphanies:** Powered by **Google Gemini 2.5 Flash**, it curates a unique Persian atmospheric paragraph, a non-repetitive Persian literary quote (inside `<b>« »</b>`), and a profound English sentence (inside `<b>""</b>`).
* 💸 **Zero Server Costs:** Runs 100% on GitHub Actions. Take that, expensive cloud hosting bills!
* 🔒 **Fort Knox Memory:** Safely compresses and encrypts its state and daily logs (`music_state.enc`) using OpenSSL. It never forgets where it left off.
* 🎵 **Smart Tagging:** Automatically fetches track metadata and genres via the **iTunes API** to give the AI the perfect context.

## 🏗️ How It Works (The Two-Phase Magic)

1. **Phase 1: The Listener (`listener.yml`)** 🎧
   Runs on a schedule throughout the day. It uses Telegram's `getUpdates` to catch new audio tracks, grabs their genres from iTunes, and quietly tucks them into a local `daily_log.json`.
   
2. **Phase 2: The AI Curator (`curator.yml`)** 🦉
   Triggers exactly at **00:00 Tehran Time**. It reads yesterday's log, asks Gemini to feel the vibe of each track, and gracefully *edits* the original Telegram message to append the generated poetry. Once done, it sweeps the log clean for the next day.

## 🛠️ Setup & Deployment

Ready to invite the poet to your channel? Here is how to set the stage:

### 1. The GitHub Secrets 🤫
Go to your repository settings: `Settings > Secrets and variables > Actions` and add the following keys. Without these, the bot is deaf and mute:

| Secret Name | What is it? | Example |
| :--- | :--- | :--- |
| `MUSIC_BOT_TOKEN` | Your bot's token from [@BotFather](https://t.me/BotFather) | `123456:ABC-DEF1234ghIkl...` |
| `MUSIC_CHANNEL_ID` | Your public channel's ID (**MUST** include `-100`) | `-1001234567890` |
| `GEMINI_API_KEY` | Your Google Gemini API Key | `AIzaSyB...` |
| `DB_PASSWORD` | A strong password to encrypt the bot's memory | `SuperSecretVibePass2026!` |

### 2. Permissions 👑
Make sure your Bot is an **Admin** in your public Telegram channel with the explicit right to **Edit Messages**. 

### 3. Kick Back and Relax ☕
Once the code is pushed and the secrets are set, GitHub Actions will automatically take over based on the cron schedules. You just drop the music; the bot drops the mic.

## ⚠️ Important Quirks & Limitations

* **The Forwarded Message Curse:** Telegram has a strict architectural rule: *No one* can edit a forwarded message. If you forward a track from another channel instead of uploading it directly, Telegram will block the edit (`Bad Request: message can't be edited`). 
* **Timezone Locked:** The AI Curator is hardcoded to run and calculate "yesterday" relative to **Tehran Time (IRST)**.
* **State Conflicts:** If you manually trigger workflows at the exact same time and they overlap, Git might yell about a `Merge conflict in music_state.enc`. If that happens, just pull, resolve, and push!

---
*Built with ❤️, Python, and a touch of midnight melancholy.*
