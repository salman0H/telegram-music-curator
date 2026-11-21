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

[راهنمای فارسی اجرا، دریافت داده و خروجی JPG/فازی](#music-memory-runbook)

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
| `TASTE_MEMORY_PASSWORD` | Authenticated encrypted music-choice memory; same key as the other bot/local launcher |
| `LASTFM_API_KEY` | [Last.fm API key](https://www.last.fm/api/account/create) enabling recommendations |

Give the bot channel administrator permissions to edit messages, post messages, and pin summaries. Enable Actions on your fork. If you start with a fresh installation, remove the inherited `music_state.enc` before running; an existing archive requires its original password.

The workflow runs daily at **02:00 Tehran time** (`22:30 UTC`) and can also be started from **Actions → Music Caption Curator → Run workflow**. Scheduled Actions may start late. Telegram retains pending updates for a limited time, so daily polling can miss posts after delayed or failed runs.

The workflow decrypts `music_state.enc`, processes updates, then encrypts and commits the state and hashtag summary. Avoid overlapping manual runs because they share the same state.

## Development

Requires Python 3.12 or later. Install `requirements.txt` for encrypted memory and JPG export. Export the same environment variables listed above before running:

```sh
python3 -m pip install -r requirements.txt
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





<a id="music-memory-runbook"></a>

## راهنمای اجرا و گرفتن خروجی حافظهٔ موسیقی

### مسیر کار

```text
دریافت/انتشار آهنگ → ثبت رمزگذاری‌شده → بازیابی تگ → ذخیره در GitHub
        → Pull روی دستگاه → استخراج محلی → گزارش، نمودار JPG و JSON
```

تحلیل و گزارش‌گیری به ایجنت یا Ollama نیاز ندارند. بازیابی ژانرِ آهنگ‌های
بدون تگ، با اجازهٔ صاحب حساب، نام آهنگ و خواننده را به iTunes می‌فرستد.
فایل صوتی، متن پیام و کلید ارسال نمی‌شوند. فقط نتیجه‌ای پذیرفته می‌شود که
نام آهنگ و خواننده‌اش پس از یکسان‌سازی نوشتار تطبیق داشته باشند.

### ۱. اجرای بات یا بازیابی فوری تگ در GitHub

- برای کار معمول بات، از ورک‌فلو اصلی همین مخزن استفاده کن؛ اجرای معمول،
  مرحلهٔ بازیابی تگ و ذخیرهٔ حافظه را هم دارد.
- برای بازیابی تگ بدون ارسال پیام به تلگرام و بدون فراخوانی ایجنت، وارد
  **Actions → Backfill encrypted music tags → Run workflow → main** شو.
- تا موفق‌شدن مراحل **Verify authenticated tag memory** و
  **Persist encrypted tag memory** صبر کن؛ سپس Pull بگیر.

کلید حافظه در Secret به نام `TASTE_MEMORY_PASSWORD` قرار دارد. برای ادغام
دو بات، کلید هر دو مخزن و کلید محلی باید یکسان باشند. این کلید با
`DB_PASSWORD` آرشیو قدیمی Curator یکی فرض نمی‌شود.

در لاگ، `after_events` تعداد رکوردها و `after_tagged` تعداد موارد دارای تگ
معتبر است. پیام `authenticated journal PASS` همراه `tagged=...` نشان می‌دهد
فایل نوشته‌شده دوباره رمزگشایی و بررسی شده است. نام آهنگ‌ها در لاگِ این
مرحله چاپ نمی‌شود.

در هر اجرا حداکثر ۵۰ جست‌وجوی کاتالوگ انجام می‌شود؛ درخواست‌ها حداقل ۳٫۱ ثانیه
فاصله دارند و نتایج منفی پس از یک روز دوباره قابل بررسی‌اند. نبود نتیجهٔ
معتبر، تگ حدسی ایجاد نمی‌کند. `TASTE_TAG_LOOKUP_LIMIT=0` جست‌وجوی کاتالوگ را
غیرفعال می‌کند و فقط منابع محلی/آرشیوی بررسی می‌شوند.

### ۲. نصب ابزار مشترک محلی، فقط یک‌بار

دستورهای زیر برای چیدمان فعلی دستگاه سلمان هستند؛ سه پوشهٔ `idea-planning`،
`telegram-music-curator` و `telegram-vibe-agent` کنار هم قرار دارند. لانچر مشترک
`music_memory_local.py` داخل پوشهٔ `idea-planning` است، نه داخل این مخزن.

```bash
cd /Users/salman/Projects/idea-planning
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Python 3.12 یا جدیدتر لازم است. ابزار کلید فعلی را خودش از
`.secrets/music-memory-password` می‌خواند. مقدار کلید را در دستور، README یا
چت ننویس و برای بازکردن فایل موجود، کلید جدید تولید نکن.

### ۳. دریافت دادهٔ تازه و ساخت همهٔ خروجی‌ها

```bash
git -C /Users/salman/Projects/telegram-music-curator pull --ff-only origin main
git -C /Users/salman/Projects/telegram-vibe-agent pull --ff-only origin main

cd /Users/salman/Projects/idea-planning
.venv/bin/python music_memory_local.py extract
```

`extract` اینترنت یا ایجنت را فراخوانی نمی‌کند؛ فایل‌های **قبلاً پول‌شده** را
می‌خواند. همان پیام کانال دوباره شمرده نمی‌شود؛ بیشترین وزن منبع باقی
می‌ماند. سابقهٔ محلی با هر استخراج از صفر ساخته نمی‌شود. پیش از تغییر
حافظه، نسخهٔ قبلی به‌صورت رمزگذاری‌شده در `private/backups/` نگه داشته می‌شود.

### ۴. خروجی‌ها کجا هستند؟

همهٔ فایل‌های زیر داخل `/Users/salman/Projects/idea-planning/private/` هستند:

| فایل | کاربرد |
|---|---|
| `music-vibe.jpg` | ده تگ با بیشترین وزن، پوشش تگ و تعداد ارسال‌ها در بخش‌های روز |
| `music-fuzzy.jpg` | عضویت فازی زمان و نمودار جداگانهٔ احساس/انرژی موسیقی |
| `extracted-summary.json` | آمار تجمیعی فعلی برای پردازش محلی |
| `fuzzy-summary.json` | آمار فازی و مختصات مشتق‌شده برای تحلیل محلی |
| `agent-summary.txt` | گزارش متنی تجمیعی برای بازبینی و استفادهٔ احتمالی ایجنت |
| `music_memory.enc` | حافظهٔ مشترک رمزگذاری‌شده |
| `aggregate_history.enc` | تاریخچهٔ رمزگذاری‌شدهٔ خلاصه‌ها |

تصویرها JPG واقعی‌اند. برای بازکردن روی مک، از پوشهٔ `idea-planning` اجرا کن:

```bash
open private/music-vibe.jpg
open private/music-fuzzy.jpg
open private/agent-summary.txt
```

### ۵. فقط یک خروجی لازم داری؟

```bash
cd /Users/salman/Projects/idea-planning
.venv/bin/python music_memory_local.py chart
.venv/bin/python music_memory_local.py report
.venv/bin/python music_memory_local.py fuzzy
```

به‌ترتیب: فقط نمودار تگ‌ها، گزارش متنی، یا نمودار/JSON فازی. هر فرمان، فایل‌های
پول‌شده را ابتدا ادغام می‌کند و `extracted-summary.json` را هم تازه می‌کند.
گزینهٔ قدیمی `--analyze` ضروری نیست؛ قواعد محلی همیشه دوباره محاسبه می‌شوند.

### ۶. نتیجه و محدودیت‌ها را چگونه بخوانی؟

- `merged_events`: تعداد رکوردهای نهایی؛ `recognized_tag_events`: تعداد موارد
  دارای حداقل یک تگ شناخته‌شده؛ `timestamped`: موارد دارای زمان اصلی ارسال.
- `sources_found` معمولاً ۲ و `sources_missing` معمولاً صفر است. نبود فایل یک
  مخزن به‌معنی نبودن سابقهٔ واقعی آن نیست؛ اجرای موفق و Pull آن را بررسی کن.
- انتخاب مستقیم و منتشرشدهٔ ادمین در Vibe وزن ۳ دارد؛ مشاهدهٔ کانال و آرشیو
  وزن ۱ دارند. یک آهنگ می‌تواند چند تگ داشته باشد، پس مجموع وزن تگ‌ها برابر
  تعداد آهنگ‌ها نیست.
- هشتگ‌های اصلی حتی اگر ناشناخته باشند در `raw_tag_observations` داخل حافظهٔ
  رمزگذاری‌شده می‌مانند؛ گزارش فقط تگ‌های شناخته‌شده را می‌آورد.
- تگ‌های آرشیو و کاتالوگ منشأ جداگانهٔ `archive_genre` و `catalog_genre` دارند.
- نمودار زمانی از زمان ارسال استفاده می‌کند؛ زمان اجرای بات جایگزین آن نمی‌شود.
  تاریخِ ناموجود برای رکورد قدیمی حدس زده نمی‌شود.
- نمودار فازی احساس به **هر دو** تگِ جهت احساس (`sad`/`happy`/`neutral`) و انرژی
  (`calm`/`energetic`) نیاز دارد. خالی‌بودن این بخش با پیام کمبود شواهد طبیعی است.
- عضویت فازی احتمال نیست؛ ژانرهایی مثل Rock یا Metal اثبات‌کنندهٔ غم، شادی یا
  وضعیت روانی تو نیستند.

### ۷. مرز اطلاعاتی ایجنت و نگهداری امن

فقط متن بازبینی‌شدهٔ `agent-summary.txt` را همراه یکی از پرامپت‌های
[`aggregate_review.txt`](prompts/aggregate_review.txt) یا
[`psychological_reflection.txt`](prompts/psychological_reflection.txt) استفاده کن.
گزارش، نام آهنگ/خواننده، شناسه‌ها، کپشن، لینک، زمان دقیق، کلید یا ciphertext
ندارد. فایل خام `.enc`، کلید، لاگ و `fuzzy-summary.json` جایگزین آن نیستند.
فایل فازی برای تحلیل محلی است و می‌تواند مختصات مشتق‌شدهٔ تک‌مشاهده داشته باشد.

خلاصهٔ تکراری دوباره در تاریخچه ثبت نمی‌شود و متن، حداکثر شش خلاصهٔ اخیر را
نشان می‌دهد. گزارش‌های هم‌پوشان شاهد مستقل جدید نیستند. گزارش و JPG هم خصوصی
هستند؛ آن‌ها را وارد Git نکن. اتصال خودکار به ایجنت تحلیل‌گر هنوز ساخته نشده؛
کپشن‌نویسی فعلی Vibe با Groq، مسیری جدا با ورودی‌های قبلی خودش است.

### ۸. عیب‌یابی

| مشکل | اقدام |
|---|---|
| خطای نبود `PIL` یا `cryptography` | نصب `requirements.txt` را با همان `.venv/bin/pip` تکرار کن. |
| `InvalidToken` یا خطای رمزگشایی | کلید فعلی، یکسان‌بودن Secrets و سلامت فایل را بررسی کن؛ حافظه را حذف نکن. |
| داده یا نمودار قدیمی است | موفق‌شدن اجرای GitHub، سپس Pull و در پایان `extract` را بررسی کن. |
| آهنگ بدون تگ است | سقف بررسی هر اجرا، نبود تطبیق یا ژانر ناموجود/ناشناخته را در لاگ ببین. |
| زمان آرشیوی نامشخص است | زمان اصلی موجود نبوده؛ نباید با زمان اجرای امروز جایگزین شود. |
| بخش احساس فازی خالی است | نبود تگ صریح احساس/انرژی؛ ژانر به‌تنهایی کافی نیست. |

تست‌های همین مخزن:

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
```

برای جزئیات کامل اجرای اختیاری بات‌ها روی دستگاه و نقش هر فایل، راهنمای محلی
`/Users/salman/Projects/idea-planning/README.md` را بخوان.

### مبنای روش‌ها

- [Mamdani inference](https://www.mathworks.com/help/fuzzy/fuzzy-inference-process.html)
- [Centroid defuzzification](https://www.mathworks.com/help/fuzzy/defuzzification-methods.html)
- [Apple Search API](https://performance-partners.apple.com/search-api)

قواعد فازی و ابزار مقایسهٔ خطای روش با برچسب انسانی در `scripts/fuzzy_mood.py`
و `scripts/evaluate_mood.py` هستند. تست درست‌بودن پیاده‌سازی، اعتبار تشخیص
روان‌شناختی ایجاد نمی‌کند.
