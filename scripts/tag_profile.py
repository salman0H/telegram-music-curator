"""Offline deterministic tag aggregation and strictly allowlisted text export."""
import re
from pathlib import Path
import os

VERSION = 'weighted-tags-v1'
# Genre/style tags stay descriptive; they are never translated into human mood.
STYLE = ('dark','ambient','chill','dreamy','instrumental','soundtrack','classical','indie',
         'alternative','pop','rock','punk','grunge','metal','hiphop','rap','trap','rnb',
         'soul','funk','jazz','blues','electronic','folk','acoustic','country','persian',
         'persianpop','persiantraditional','persianrock','persianrap','persianalternative',
         'dance','singersongwriter','newage','children','world','reggae','latin','kpop','gospel','holiday','comedy')
ALIASES = {name:name for name in STYLE}
ALIASES.update({'hiphoprap':'hiphop','rbsoul':'rnb','alternativerock':'alternative',
                'progressiverock':'rock','hardrock':'rock','heavymetal':'metal','dancemusic':'dance',
                'sad':'sad','غمگین':'sad','غم':'sad','happy':'happy','شاد':'happy',
                'neutral':'neutral','خنثی':'neutral','calm':'calm','آرام':'calm',
                'energetic':'energetic','پرانرژی':'energetic'})
SAFE = frozenset(ALIASES.values())
SOURCE_WEIGHTS = {'vibe_admin':3,'vibe_channel':1,'curator_channel':1,'vibe_queue':1}
BUCKETS = ('night','morning','afternoon','evening','unknown')

def extract_tags(text):
    return re.findall(r'(?<!\w)#([\w\u200c]+)', text or '')

def canonical(tags):
    return sorted({ALIASES[key] for tag in tags if isinstance(tag,str)
                   for key in [re.sub(r'[^\w]+', '', tag.strip().lstrip('#').casefold()).replace('_','').replace('\u200c','')]
                   if key in ALIASES})

def from_tags(tags):
    tags=canonical(tags)
    valences=[v for tag,v in [('sad',-1),('neutral',0),('happy',1)] if tag in tags]
    energies=[v for tag,v in [('calm',0),('energetic',1)] if tag in tags]
    value=sum(valences)/len(valences) if valences else None
    label='unknown' if value is None else 'mixed' if 'sad' in tags and 'happy' in tags else 'sad' if value<0 else 'happy' if value>0 else 'neutral'
    return dict(label=label,valence=value,energy=sum(energies)/len(energies) if energies else None,
                tags=tags,confidence=1 if valences else 0,basis=VERSION,model=None)

def profile(store):
    totals={}
    buckets={name:{'events':0,'tagged':0,'weighted_tags':{}} for name in BUCKETS}
    tagged=0
    for event in store['events'].values():
        tags=canonical([tag for values in event.get('tag_observations',{}).values() for tag in values])
        weight=max((SOURCE_WEIGHTS.get(source,1) for source in event.get('sources',[])),default=1)
        bucket=event.get('time_bucket','unknown')
        bucket=bucket if bucket in buckets else 'unknown'
        group=buckets[bucket]
        group['events']+=1
        if tags:
            tagged+=1
            group['tagged']+=1
        for tag in tags:
            totals[tag]=totals.get(tag,0)+weight
            group['weighted_tags'][tag]=group['weighted_tags'].get(tag,0)+weight
    return dict(method=VERSION,events=len(store['events']),tagged=tagged,weighted_tags=totals,time_buckets=buckets)

def _clean_summary(summary):
    def count(value):
        if type(value) is not int or value < 0:
            raise ValueError('Invalid aggregate count')
        return value
    def tags(values):
        return {tag: count(values[tag]) for tag in SAFE if tag in values}
    return {'events':count(summary['events']), 'tagged':count(summary['tagged']),
            'weighted_tags':tags(summary['weighted_tags']),
            'time_buckets':{name:{'events':count(group['events']), 'tagged':count(group['tagged']),
                                  'weighted_tags':tags(group['weighted_tags'])}
                            for name,group in summary['time_buckets'].items() if name in BUCKETS}}

def render_summary(summary):
    summary=_clean_summary(summary)
    lines=['AGGREGATE MUSIC TAG REPORT', 'Method: '+VERSION,
           f"Observed events: {summary['events']}; events with recognized tags: {summary['tagged']}.",
           'Weights: direct admin selection 3; other observations 1; duplicate post uses max.',
           'Counts are weighted observations, not probabilities or psychological measurements.',
           'Missing tags mean unknown. Style tags do not establish happiness or sadness.',
           'This report contains no track names, artists, user/chat/message IDs, links, captions, exact dates, keys or encrypted records.',
           'Overall recognized tags:']
    # Only values produced by this module are rendered; no raw free text is echoed.
    lines += [f'- {tag}: {score}' for tag,score in sorted(summary['weighted_tags'].items())]
    if not summary['weighted_tags']: lines.append('- No recognized tags available.')
    lines.append('Broad time buckets (groups under 3 events suppressed):')
    for name,group in summary['time_buckets'].items():
        if group['events']>=3:
            lines.append(f"- {name}: {group['events']} events; {group['tagged']} tagged; " +
                         ', '.join(f'{tag}={score}' for tag,score in sorted(group['weighted_tags'].items())))
    lines.append('No causal inference, diagnosis or claim about the listener mood is supported.')
    return '\n'.join(lines)+'\n'

def report_text(store):
    return render_summary(profile(store))

def export_report(store,path,history_path=None,password=None):
    summary=profile(store)
    text=render_summary(summary)
    if history_path:
        from taste_memory import read_store,write_store
        import fcntl
        history_path=Path(history_path)
        history_path.parent.mkdir(parents=True,exist_ok=True)
        with open(str(history_path)+'.lock','a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            history=read_store(history_path,password)
            snapshots=history.setdefault('aggregate_snapshots',[])
            summary=_clean_summary(summary)
            if not snapshots or snapshots[-1]['profile'] != summary:
                snapshots.append({'sequence':len(snapshots)+1,'profile':summary})
                write_store(history_path,password,history)
            text='LONGITUDINAL AGGREGATE REPORT\nSnapshots may overlap; they are not independent new observations.\n'
            for snapshot in snapshots[-6:]:
                # Render only whitelisted counts; never echo stored free text.
                text += f"\nSnapshot {int(snapshot['sequence'])}:\n"+render_summary(snapshot['profile'])
    # Export is deliberate plaintext; owner-only permissions from creation.
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as stream:stream.write(text)
    os.chmod(path,0o600)
