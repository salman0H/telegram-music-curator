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

Music Curator reads new audio posts from a Telegram channel, looks up their metadata, and builds a compact caption with up to three genre hashtags. Similar tracks appear in that same text as **artist — song title**: no artist biographies, links, or explanations.

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
4. The caption includes up to three distinct artist/title pairs, excluding the source recording. Titles appear as a bulleted list under **🎧 آهنگ‌های پیشنهادی**, are HTML-escaped, and are appended only when they fit Telegram's caption limit.

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




## Offline weighted-tag memory (current default)

The memory/analysis feature runs locally **without Ollama, an agent, a model key
or network requests**. The old metadata-to-Ollama analysis path has been removed;
`TASTE_OLLAMA_MODEL` no longer enables it. Vibe Agent's existing Groq poetry/caption
feature remains separate and unchanged; it still uses its existing inputs.

### Recording and basic analysis

Set `TASTE_MEMORY_PASSWORD` locally or as an Actions secret to enable the
independent authenticated encrypted journal `data/taste_memory.enc`. Install
`requirements.txt`. Without the password, recording is disabled.
Raw music metadata stays inside the encrypted journal. Owner-only local key
files belong in `.secrets/`, which is ignored; never publish the password.

Existing hashtags and Curator genre tags are normalized against the fixed
allowlist in `scripts/tag_profile.py`. Source-tag observations retain provenance
inside the journal. Only explicit sad/happy/neutral/calm/energetic tags and their
listed Persian aliases inform deterministic affect rules. Dark, metal, chill,
ambient and similar style tags remain descriptive; they do not establish the
listener's feelings. No emotion is guessed from a title, artist, genre or hour.
Conflicting sad/happy tags remain mixed. Missing valence or energy stays unknown.

Direct admin-selected Vibe posts have preference weight 3; channel observations
and legacy queue observations have weight 1. Re-observing the same channel/message
uses max source weight and counts each canonical tag once, even if both bots
observe it. A raw genre frequency is not a psychological score or probability.
Mamdani fuzzy tools remain available for explicit valence/energy evidence, but
the default chart/report is the simpler deterministic weighted-tag summary.
New observations retain rule/version provenance inside authenticated encryption.

The original Telegram send time is retained with timezone Asia/Tehran. Basic
charts group by calendar hour. Broad day buckets and circular time memberships
are descriptive grouping tools; time never changes a song's valence.

### Local outputs, no agent transmission

```sh
python scripts/taste_memory.py /path/curator.enc /path/vibe.enc --chart /private/tmp/music-tags.jpg
python scripts/taste_memory.py /path/curator.enc /path/vibe.enc --report /private/tmp/agent-summary.txt --history /private/path/aggregate_history.enc
```

Both commands read `TASTE_MEMORY_PASSWORD` from the environment. `--analyze`
now only recomputes explicit-tag rules offline; it never calls a model.
The plaintext report is a deliberate export with owner-only permissions, not
a decrypted record dump. It includes only allowlisted tag totals, source-weight
rules, coverage and coarse time buckets; buckets under three events are suppressed.
Track/artist names, captions, links, exact timestamps, identifiers, keys and
ciphertext are excluded by construction. Aggregate reports still contain private
preferences; keep exported reports out of Git. No external agent is connected or
automatically called by this feature.

The optional `--history` file retains aggregate-only snapshots under the same
authenticated encryption. Unchanged snapshots are not duplicated. The plaintext
export includes at most the latest six snapshots for longitudinal comparison;
all snapshots remain in encrypted history. Overlapping snapshots are not new
independent evidence and must not be counted as extra observations.

Prepared templates in `prompts/aggregate_review.txt` and
`prompts/psychological_reflection.txt` accept only the aggregate text report.
They require competing explanations, uncertainty, missing-coverage disclosure and
non-leading questions. Psychological reflection must distinguish music patterns,
explicit self-report and tentative interpretation; it must not diagnose or equate
musical sadness with the listener's mental state. Prompt wording reduces leading
framing but cannot guarantee an unbiased model or clinical validity.

### Verification and limitations

```sh
python -m unittest discover -s tests -v
python scripts/verify_taste_memory.py
```

Writes use Fernet authenticated encryption with scrypt-derived keys, fresh salts,
atomic replacement and local locking. Wrong passwords/corrupt files do not reset
history. Recording failure does not stop normal bot processing, so failed records
may need recovery. Actions explicitly persists the encrypted journal, not its key.
Separate repositories retain separate journals; the local command merges them.
Historical records without tags remain unknown; old model guesses are not used
as observed tags. Existing non-memory bot logs retain their prior privacy behavior.

### Auditable methods

Mamdani min implication/max aggregation and 401-point centroid defuzzification,
circular time membership and the held-out MAE evaluation tool remain in
`scripts/fuzzy_mood.py` and `scripts/evaluate_mood.py`. They do not validate a
psychological conclusion. Model confidence is not calibrated probability;
unequal-weight effective sample size is not a confidence interval.

- [Mamdani inference process](https://www.mathworks.com/help/fuzzy/fuzzy-inference-process.html)
- [Centroid defuzzification](https://www.mathworks.com/help/fuzzy/defuzzification-methods.html)
- [Music-emotion benchmark DEAM](https://cvml.unige.ch/databases/DEAM/)
- [Unequal-weight effective sample size](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.gaussian_kde.html)

The feature records the owner's selected music. It does not authorize undisclosed
collection of other people's personal profiles; see
[Telegram content terms](https://telegram.org/tos/content-licensing).

JPEG chart output uses Pillow and includes aggregate tag coverage and time buckets.
Local chart files contain private preference summaries; do not commit them.


## Local tag preservation and fuzzy JPG

Original hashtags are now retained under `raw_tag_observations` inside the
 encrypted journal even when the canonical allowlist does not recognize them.
Only canonical tags enter aggregate text exports. Common Hip-Hop/Rap, R&B/Soul
and compound genre spellings are normalized without inventing emotions.
Existing records without original tags cannot be reconstructed from song names
alone. Catalog enrichment is enabled separately as explicitly authorized by the owner.

```sh
python scripts/taste_memory.py /private/path/memory.enc --fuzzy-chart /private/tmp/music-fuzzy.jpg --fuzzy-report /private/tmp/fuzzy-summary.json
```

The fuzzy JPG shows actual source-weighted circular time memberships separately
from musical affect. Missing valence/energy yields an explicit empty affect
panel; genre and time never fabricate happiness, sadness or personal wellbeing.
The JSON is a local derived analysis artifact, not the agent plaintext export.


## Automatic non-AI tag enrichment (owner-authorized)

`backfill_taste_tags.py` runs after normal processing, independently of Groq or
Telegram caption-edit success. Curator imports its existing per-song genre index.
For still-untagged songs, only artist/title are sent to the iTunes music catalog;
no audio, message bodies or keys are sent. A catalog genre is accepted only when
both artist and title match after Unicode/punctuation normalization. Wrong first
results, unknown identities and missing catalog coverage never fabricate a tag.

Archive and catalog tags retain distinct `archive_genre` / `catalog_genre`
provenance inside encryption. Selection weights remain unchanged. Musical genres
never become psychological mood labels. Unmatched lookups retry after one day;
results are cached per run and requests are spaced at least 3.1 seconds apart,
with at most 50 lookups per run. `TASTE_TAG_LOOKUP_LIMIT=0` disables catalog calls.

Manual Actions workflow **Backfill encrypted music tags** performs this same
real-data repair, verifies decryption/tag counts, and commits only the encrypted
journal. It does not post to Telegram or call an AI agent. The regular bot
workflows also persist the enriched journal using their existing concurrency
lock. Tag coverage and failure statuses can be inspected without logging songs.

[Apple Search API documentation](https://performance-partners.apple.com/search-api)
