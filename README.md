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


## Optional private music-choice memory

Set `TASTE_MEMORY_PASSWORD` locally or as an Actions secret to enable an
independent authenticated encrypted journal at `data/taste_memory.enc`.
Without the secret recording is disabled. Install `requirements.txt`.
Use the same strong password in both repositories to merge their journals locally.
No credentials or real choice history are included in this change.

Each event retains channel/message identity, artist/title, original Telegram
send time, Tehran time bucket, source, preference weight and musical mood.
Direct admin selections published through Vibe Agent have weight **3**;
channel observations have weight **1**. These are configurable design constants,
not measured probabilities. Duplicate observations of the same channel message
use the maximum weight. Reposting on a different message remains a new choice.
Auto-pins and generated captions never count as personal likes.

Mood is **unknown by default**. Optional `TASTE_OLLAMA_MODEL` enables the local
Ollama service at `127.0.0.1:11434` to estimate known recordings' musical mood
from artist/title, with confidence and provenance. This does not analyze audio
or lyrics and model confidence is not calibrated accuracy. Unknown and low
confidence results are excluded from averages. No personal emotional/mental
state is inferred. `self_reported_mood` is reserved for explicit user input.
Actions runners do not have your local Ollama service; classification there
remains unknown. Missing historical send times stay unknown.

Generate a private chart on your own device (SVG is decrypted, do not commit it):

```sh
python scripts/taste_memory.py /path/curator/taste_memory.enc /path/vibe/taste_memory.enc --chart /private/tmp/music-taste.svg
```

The chart shows source × confidence weighted Mamdani musical valence per Tehran calendar hour,
classified/total coverage, and unknown observations. It is not a wellbeing chart.
The CLI requires `TASTE_MEMORY_PASSWORD` in the environment. Authenticated
Fernet encryption uses a fresh salt and scrypt key derivation; writes are atomic
and local writers share an advisory lock. A wrong password/corrupt file never
resets history; errors are logged without sensitive contents and the bot continues.
Keep backups: if persistence fails, the main bot can acknowledge an update and
that observation may need manual recovery. Retain the password separately.

The existing bot architecture, Telegram publication, and music recommendations
stay in place. This feature records choices; it does not modify recommendation
ranking or editorial captions. Actions commits only this new encrypted journal;
existing repository logs/state have their original privacy behavior. Local use
can point both bots at the same absolute `TASTE_MEMORY_FILE`; separate Actions
repositories retain independent files merged by the local chart command.

For journals recorded on Actions, run the chart command with `--analyze`
and `TASTE_OLLAMA_MODEL` on your own machine to fill unknown moods locally.
No external model API is used by the new memory feature.

Legacy Vibe editorial queue observations are retained as `vibe_queue` with
weight 1 because their personal-selection provenance is unknown. Future admin
uploads retain their timestamp and explicit admin source through queue retries.


## Reproducible fuzzy music analysis

Both bots share the same versioned `fuzzy_mood.py` algorithm. This is a
**Mamdani min–max system with centroid defuzzification**, not a trained emotion
recognizer or a measurement of personal wellbeing. No additional dependency is
needed and the existing bot routing/encrypted journal format remains compatible.

The valence/arousal framework is established in music-emotion research, e.g.
[DEAM](https://cvml.unige.ch/databases/DEAM/) and its
[benchmark paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC5345802/).
Our metadata-model `energy` field is only a proxy for perceived musical arousal;
it is not a validated acoustic arousal measurement. DEAM was not used to train,
tune or validate this implementation; dataset use needs its own license review.

### Inputs, memberships and rules

- Inputs: musical valence `v ∈ [-1,1]`, energy `e ∈ [0,1]`, and upstream
  model confidence `c ∈ [0,1]`. Missing/non-finite/invalid inputs or `c < 0.7`
  cause abstention. No unknown recording is silently assigned neutral mood.
- On `x ∈ [-1,1]`, membership functions are `negative=max(0,-x)`,
  `neutral=1-abs(x)`, `positive=max(0,x)`. Valence uses `x=v`; energy uses
  `x=2e-1`. Each three-set partition sums to one.
- The nine rules are the Cartesian product of sad/neutral/happy and
  calm/moderate/energetic. For example: IF valence is sad AND energy is calm,
  THEN musical mood is sad_calm. Every active rule and its activation are retained.
- AND/implication uses minimum; aggregation uses maximum. The two output
  coordinates retain their respective linguistic terms. A 401-point
  trapezoidal centroid converts the aggregated output sets to numerical scores.
  These are fuzzy indices, not the original input scale or validated human ratings.
- A membership degree expresses compatibility with a linguistic set. It is
  **not a probability**, and model self-confidence is not calibrated accuracy.

New/updated observations include `fuzzy_music` (method version, active rules,
memberships, scores) and circular `time_memberships`. Existing encrypted files
remain readable; charts recompute derived fuzzy values without requiring migration.
Local `--analyze` also refreshes derived fields after optional Ollama estimation.

Time memberships use circular triangular windows centered at 03:00, 09:00,
15:00 and 21:00 in recorded Tehran time, each with radius six hours. Thus
midnight belongs equally to evening and night instead of jumping abruptly.
Time groups choices; it never changes a recording's valence or infers your mood.

### Aggregation and honest uncertainty

Within each calendar-hour group, each classified recording has analysis weight
`source_weight × model_confidence`. Source priority remains admin-selected Vibe
3, other observations 1; observations of the same channel/message use max source
weight rather than adding duplicate evidence. The hourly fuzzy index is the
weighted mean of defuzzified musical-valence scores. Charts show classified/total
coverage and Kish effective sample size `(sum(w))² / sum(w²)`.

Kish n_eff describes unequal weight concentration; it does not establish
independence, statistical significance, confidence intervals or psychological
validity. Memberships, thresholds, source weights and rules are heuristic choices.
The pipeline does not claim that fuzzy processing improves prediction accuracy.
No accuracy scores are fabricated from unlabelled listening history.

### Validate before trusting predictions

```sh
python -m unittest discover -s tests -v
python scripts/evaluate_mood.py /private/path/held-out-labels.json
```

The evaluation file is a JSON array of objects with `model_valence`,
`human_valence` (both -1 to 1), `energy` (0 to 1) and `confidence` (0 to 1).
Human labels describe the **music**, not the listener. Collect your labels before
viewing predictions; freeze the model/rules and evaluate on separate recordings
and preferably held-out artists. Start with at least 50 diverse judgements for
an exploratory comparison, not a statistical guarantee. Report coverage and MAE
for both raw-model and fuzzy scores on the same accepted items. Lower MAE is
better; if fuzzy is worse, keep the raw baseline and revise the rules using a
separate development set. Self-reported personal mood needs a distinct target
and its own evaluation; it is never manufactured from music choices.

Tests cover analytic centroid reference values (shoulders ±2/3, center zero),
partition coverage, symmetry, monotonicity, overlapping rules, invalid inputs,
midnight continuity, weighting/n_eff and baseline evaluation. These establish
implementation behavior, **not empirical validity of music-emotion recognition**.

### Method references

- [MathWorks: fuzzy inference process](https://www.mathworks.com/help/fuzzy/fuzzy-inference-process.html)
  — fuzzification, rules, implication, aggregation and defuzzification.
- [MathWorks: centroid defuzzification](https://www.mathworks.com/help/fuzzy/defuzzification-methods.html)
  — center of gravity of the aggregated output set.
- [SciPy: effective number of datapoints](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.gaussian_kde.html)
  — unequal-weight effective sample size formula. This project computes only
  that diagnostic; it does not use KDE or claim independent observations.

### Telegram collection scope

This feature records the owner's music choices. It does not turn either bot
into an undisclosed collector of third-party personal profiles. A user-account
client (MTProto) is different from a Bot API bot; client authorization does not
expand what content the account is entitled to access. Telegram limits AI data
harvesting and requires explicit, informed, continued consent in the specific
context for its stated exception. Group membership or public availability alone
is not that consent. See [content licensing terms](https://telegram.org/tos/content-licensing)
and [Bot FAQ](https://core.telegram.org/bots/faq#what-messages-will-my-bot-get).
