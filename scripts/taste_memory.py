"""Optional encrypted music-choice journal. Never infers the listener's mental state."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fuzzy_mood import infer, time_memberships
from tag_profile import from_tags, extract_tags, canonical, export_report, profile

SCHEMA = 1
WEIGHTS = {'vibe_admin': 3, 'vibe_channel': 1, 'curator_channel': 1, 'vibe_queue': 1}

def _crypto(password, salt):
    from cryptography.fernet import Fernet
    key = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return Fernet(base64.urlsafe_b64encode(key))

def read_store(path, password):
    path = Path(path)
    if not path.exists():
        return {'schema_version': SCHEMA, 'events': {}}
    envelope = json.loads(path.read_text())
    if envelope['schema_version'] != SCHEMA:
        raise ValueError('Unsupported memory version')
    salt = base64.b64decode(envelope['salt'], validate=True)
    value = json.loads(_crypto(password, salt).decrypt(envelope['ciphertext'].encode()))
    if value['schema_version'] != SCHEMA or not isinstance(value['events'], dict):
        raise ValueError('Invalid memory')
    return value

def write_store(path, password, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    salt = os.urandom(16)
    envelope = {'schema_version': SCHEMA, 'kdf': 'scrypt-N16384-r8-p1',
                'salt': base64.b64encode(salt).decode(),
                'ciphertext': _crypto(password, salt).encrypt(json.dumps(value, ensure_ascii=False).encode()).decode()}
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.taste-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(envelope, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def classify(artist, title):
    """Compatibility API. Names never enter a model; absent tags remain unknown."""
    return from_tags([])


def record(channel, message_id, artist, title, sent_at, source, tags=None):
    password = os.environ.get('TASTE_MEMORY_PASSWORD')
    if not password:
        return False
    try:
        if not channel or not message_id or source not in WEIGHTS:
            raise ValueError('Missing event identity')
        path = Path(os.environ.get('TASTE_MEMORY_FILE', 'data/taste_memory.enc'))
        # Lock file inode stays stable across atomic replacements; shared local paths are safe.
        import fcntl
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(path) + '.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            store = read_store(path, password)
            key = f'{channel}:{message_id}'
            event = store['events'].get(key)
            if event is None:
                stamp = int(sent_at) if sent_at else None
                local = datetime.fromtimestamp(stamp, timezone.utc).astimezone(ZoneInfo('Asia/Tehran')) if stamp else None
                event = {'channel_id': str(channel), 'message_id': message_id,
                         'artist': artist, 'title': title, 'sent_at_utc': stamp,
                         'local_time': local.isoformat() if local else None,
                         'time_zone': 'Asia/Tehran',
                         'time_bucket': ('night' if local.hour < 6 else 'morning' if local.hour < 12 else 'afternoon' if local.hour < 18 else 'evening') if local else 'unknown',
                         'observed_at_utc': datetime.now(timezone.utc).isoformat(),
                         'sources': [], 'music_mood': classify(artist, title),
                         'self_reported_mood': None}
                store['events'][key] = event
            if source not in event['sources']:
                event['sources'].append(source)
            # Same channel post observed by both bots gets max weight, never summed.
            event['preference_weight'] = max(WEIGHTS[s] for s in event['sources'])
            observations = event.setdefault('tag_observations', {})
            if tags is not None:
                raw = event.setdefault('raw_tag_observations', {})
                raw[source] = sorted(set(raw.get(source, []) + [tag[:100] for tag in tags if isinstance(tag, str)][:100]))
                observations[source] = canonical(observations.get(source, []) + list(tags))
            event['music_mood'] = from_tags([tag for values in observations.values() for tag in values])
            event['fuzzy_music'] = infer(event['music_mood'])
            event['time_memberships'] = time_memberships(event['local_time'])
            write_store(path, password, store)
            if read_store(path, password) != store:
                raise ValueError('Journal readback differs from written data')
        print(f'[taste_memory] encrypted record verified: source={source}, weight={event["preference_weight"]}')
        return True
    except Exception as error:
        # No passwords, metadata or API response contents in logs. Never overwrite bad stores.
        print(f'[taste_memory] record not saved ({type(error).__name__})')
        return False

def merge(stores):
    result = {'schema_version': SCHEMA, 'events': {}}
    for store in stores:
        for key, event in store['events'].items():
            if key not in result['events']:
                result['events'][key] = dict(event)
            else:
                old = result['events'][key]
                sources = sorted(set(old['sources'] + event['sources']))
                if event['music_mood']['confidence'] > old['music_mood']['confidence']:
                    old['music_mood'] = event['music_mood']
                old['sources'] = sources
                observations = old.setdefault('tag_observations', {})
                for source, tags in event.get('tag_observations', {}).items():
                    observations[source] = canonical(observations.get(source, []) + tags)
                raw=old.setdefault('raw_tag_observations', {})
                for source,tags in event.get('raw_tag_observations', {}).items():
                    raw[source]=sorted(set(raw.get(source, [])+tags))
                if event.get('catalog_tag_lookup'):
                    old['catalog_tag_lookup']=event['catalog_tag_lookup']
            result['events'][key]['preference_weight'] = max(WEIGHTS[s] for s in result['events'][key]['sources'])
    return result

def chart(store, output):
    if Path(output).suffix.lower() in ('.jpg', '.jpeg'):
        from tag_chart import render_jpg
        return render_jpg(store, output)
    if Path(output).suffix.lower() != '.svg':
        raise ValueError('Chart output must be .jpg, .jpeg or .svg')
    import html
    groups = {}
    for key, event in store['events'].items():
        if event.get('local_time'):
            groups.setdefault(event['local_time'][:13], {})[key] = event
    lines = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="%d">' % (160+44*len(groups)),
             '<rect width="100%" height="100%" fill="#101827"/>',
             '<g fill="#e5e7eb" font-family="sans-serif" font-size="14">',
             '<text x="24" y="30">Weighted explicit music tags · Asia/Tehran · NOT a measure of personal wellbeing</text>',
             '<text x="24" y="56">Offline tag rules only; missing tags stay unknown. No model or network required.</text>']
    for i, (hour, events) in enumerate(sorted(groups.items())):
        summary = profile({'events': events})
        tags = ', '.join(f'{tag}={score}' for tag,score in sorted(summary['weighted_tags'].items())) or 'unknown'
        lines.append(f'<text x="24" y="{100+i*44}">{html.escape(hour.replace("T"," "))}: {summary["tagged"]}/{summary["events"]} classified (tags); {html.escape(tags)}</text>')
    lines.append('</g></svg>')
    Path(output).write_text('\n'.join(lines))
    os.chmod(output, 0o600)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', help='Encrypted journals, same password')
    parser.add_argument('--chart', help='Private local JPG image (.jpg/.jpeg); legacy SVG also supported')
    parser.add_argument('--report', help='Deliberate plaintext aggregate text export, without raw records')
    parser.add_argument('--analyze', action='store_true', help='Recompute deterministic tag rules offline; never calls an agent')
    parser.add_argument('--history', help='Encrypted aggregate-only snapshot history for report export')
    parser.add_argument('--fuzzy-chart', help='Aggregate fuzzy time/affect JPEG output')
    parser.add_argument('--fuzzy-report', help='Derived fuzzy statistics JSON, local only')
    args = parser.parse_args()
    if not any((args.chart,args.report,args.fuzzy_chart,args.fuzzy_report)):
        parser.error('Specify --chart or --report')
    password = os.environ['TASTE_MEMORY_PASSWORD']
    stores = []
    for filename in args.files:
        path = Path(filename)
        if not path.is_file():
            raise FileNotFoundError(path)
        import fcntl
        with open(str(path) + '.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            value = read_store(path, password)
            if args.analyze:
                for event in value['events'].values():
                    event['music_mood'] = from_tags([tag for values in event.get('tag_observations', {}).values() for tag in values])
                    event['fuzzy_music'] = infer(event['music_mood'])
                    event['time_memberships'] = time_memberships(event['local_time'])
                write_store(path, password, value)
            stores.append(value)
    combined = merge(stores)
    if args.fuzzy_chart or args.fuzzy_report:
        import fuzzy_chart
        if args.fuzzy_chart:fuzzy_chart.render_jpg(combined,args.fuzzy_chart)
        if args.fuzzy_report:fuzzy_chart.export_json(combined,args.fuzzy_report)
    if args.chart:
        chart(combined, args.chart)
    if args.report:
        export_report(combined, args.report, args.history, password)
