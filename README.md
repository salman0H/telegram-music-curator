<div align="center">

# Telegram Music Curator

### Categorize a track. Find the next one.

A Telegram channel curator with genre hashtags and similar-song suggestions.<br>
Python standard library. GitHub Actions. Encrypted state.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Runtime](https://img.shields.io/badge/Runtime-GitHub_Actions-2088FF?logo=githubactions&logoColor=white)

[The experience](#the-experience) · [Recommendations](#recommendations) · [Quick start](#quick-start) · [Development](#development)

</div>

---

Music Curator reads new audio posts from a Telegram channel, looks up their metadata, and builds a compact caption with up to three genre hashtags. Similar tracks appear in that same text as song titles only: no artist biographies, links, or explanations.

## The experience

| Incoming post | Result |
| :--- | :--- |
| Audio with artist/title metadata | iTunes metadata, album/year when available, genre hashtags, and up to three suggested titles |
| Audio without complete metadata | Artist/title extracted from an `Artist - Title` filename when possible |
| Original caption cannot be edited | The same caption is sent as a reply to the audio |
| Reply also fails | A standalone caption links back to the original post |
| More than 100 new audio posts in one run | Links split across pinned messages; individual lookups and suggestions are skipped |

Batches of up to and including 100 tracks are fully categorized and recorded in `hashtag_summary.txt`, without the previous four-minute cutoff. Summary links are split across messages without truncation and pinned. Batches above 100 receive links only and do not add genre entries. Telegram update pages are collected into a persistent queue before processing; failed tracks remain queued for retry. A successful normal batch also gets a pinned summary. Previously processed message IDs and the Telegram update offset are persisted; a separate hashtag index produces `hashtag_summary.txt`.

## Recommendations

1. iTunes supplies the categorization metadata.
2. [MusicBrainz](https://musicbrainz.org/doc/MusicBrainz_API) searches for an exact title/artist match and supplies a recording MBID where available. Requests carry an identifying User-Agent and are spaced at least 1.1 seconds apart.
3. [Last.fm track.getSimilar](https://www.last.fm/api/show/track.getSimilar) retrieves similar recordings using that MBID, or artist/title when MusicBrainz has no match or the MBID yields no recommendations.
4. The caption includes up to three distinct titles, excluding the source title. Titles appear as a bulleted list under **🎧 آهنگ‌های پیشنهادی**, are HTML-escaped, and are appended only when they fit Telegram's caption limit.

Recommendations reflect Last.fm similarity data, rather than audio analysis or a guaranteed genre match. Missing credentials, unavailable services, or absent results leave the normal classification intact. MusicBrainz needs no API key for these public searches; Last.fm requires one.

Provider requests allow 15 seconds per attempt and retry transient network, rate-limit, and server failures up to twice. Logs identify the provider and HTTP/API error code without exposing API keys. The manual **Recommendation diagnostics** workflow checks the six tracks affected in run 123 without posting to Telegram.

## Quick start

Fork this repository and add these **GitHub Actions secrets** under **Settings → Secrets and variables → Actions**:

| Secret | Purpose |
| :--- | :--- |
| `MUSIC_BOT_TOKEN` | Telegram bot token from BotFather |
| `MUSIC_CHANNEL_ID` | Target channel ID, preferably its numeric `-100…` ID |
| `DB_PASSWORD` | Password used to decrypt and encrypt the state archive |
| `LASTFM_API_KEY` | [Last.fm API key](https://www.last.fm/api/account/create) enabling recommendations |

Give the bot channel administrator permissions to edit messages, post messages, and pin summaries. Enable Actions on your fork. If you start with a fresh installation, remove the inherited `music_state.enc` before running; an existing archive requires its original password.

The workflow runs daily at **02:00 Tehran time** (`22:30 UTC`) and can also be started from **Actions → Music Caption Curator → Run workflow**. Scheduled Actions may start late. Telegram retains pending updates for a limited time, so daily polling can miss posts after delayed or failed runs.

The workflow decrypts `music_state.enc`, processes updates, then encrypts and commits the state and hashtag summary. Avoid overlapping manual runs because they share the same state.

## Development

Requires Python 3.12. No third-party Python packages are needed. Export the same environment variables listed above before running:

```sh
python3 scripts/music_curator.py --dry-run
python3 -m unittest discover -s tests -v
```

Dry run performs provider lookups and builds captions without sending messages or saving local state. A normal local run uses `python3 scripts/music_curator.py`; local JSON state is plaintext, while the Actions workflow handles encryption.

| File | Responsibility |
| :--- | :--- |
| `scripts/music_curator.py` | Update processing, captions, reply fallback, and summaries |
| `scripts/recommendations.py` | MusicBrainz resolution and Last.fm suggestions |
| `scripts/caption_formatter.py` | HTML captions, hashtags, and title-only suggestions |
| `scripts/itunes_client.py` | Track metadata lookup |
| `scripts/telegram_client.py` | Telegram requests and retries |
| `scripts/state.py` | Update offset and processed-message history |
| `scripts/hashtag_index.py` | Hashtag index and readable summary |
| `data/genre_hashtags.json` | Genre-to-hashtag mappings |

The bot uses Telegram audio metadata and external catalogs; it does not listen to audio. Catalog coverage and incorrect upload metadata can affect classification and recommendations.
