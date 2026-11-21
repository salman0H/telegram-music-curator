"""Persist non-AI tags from legacy genre index and verified catalog matches.
No Telegram posting or agent API calls. Existing weights and provenance retained.
"""
import json
import os
from pathlib import Path
import time
from datetime import datetime,timezone,timedelta
from taste_memory import read_store,write_store,WEIGHTS
from tag_profile import canonical,from_tags,profile
from fuzzy_mood import infer,time_memberships
import catalog_tags

def seed_index(store,index,channel):
    if not channel:return 0
    added=0
    for tag,entries in index.items():
        for entry in entries:
            if not isinstance(entry,dict) or not entry.get('message_id'):continue
            key=f'{channel}:{entry["message_id"]}'
            if key not in store['events']:
                store['events'][key]={'channel_id':str(channel),'message_id':entry['message_id'],
                    'artist':entry.get('performer','Unknown Artist'),'title':entry.get('title','Unknown Title'),
                    'sent_at_utc':None,'local_time':None,'time_zone':'Asia/Tehran','time_bucket':'unknown',
                    'observed_at_utc':datetime.now(timezone.utc).isoformat(),'sources':['curator_channel'],
                    'preference_weight':1,'self_reported_mood':None,'tag_observations':{}}
                added+=1
            event=store['events'][key]
            observed=event.setdefault('tag_observations',{})
            observed['archive_genre']=canonical(observed.get('archive_genre',[])+[tag])
    return added

def enrich(store,limit=50,force=False,delay=3.1):
    looked_up=matched=0
    cache={}
    now=datetime.now(timezone.utc)
    for event in store['events'].values():
        observations=event.setdefault('tag_observations',{})
        # Do not use generated prose or model guesses as observed tags.
        tags=canonical([tag for values in observations.values() for tag in values])
        prior=event.get('catalog_tag_lookup',{})
        ready=True
        if prior.get('checked_at_utc') and not force:
            try:ready=(now-datetime.fromisoformat(prior['checked_at_utc']))>=timedelta(days=1)
            except ValueError:pass
        if not tags and ready and looked_up<limit:
            identity=(event.get('artist',''),event.get('title',''))
            if identity not in cache:
                cache[identity]=catalog_tags.lookup(*identity)
                looked_up+=1
                if delay:time.sleep(delay)
            result=cache[identity]
            if result['tags']:
                observations['catalog_genre']=canonical(observations.get('catalog_genre',[])+result['tags'])
                matched+=1
            event['catalog_tag_lookup']={k:v for k,v in result.items() if k!='tags'}
            event['catalog_tag_lookup']['checked_at_utc']=now.isoformat()
        event['music_mood']=from_tags([tag for values in observations.values() for tag in values])
        event['fuzzy_music']=infer(event['music_mood'])
        event['time_memberships']=time_memberships(event.get('local_time'))
        event['preference_weight']=max((WEIGHTS.get(source,1) for source in event.get('sources',[])),default=1)
    return {'catalog_lookups':looked_up,'catalog_matched_events':matched}

def main():
    password=os.environ.get('TASTE_MEMORY_PASSWORD')
    if not password:
        print('[tag_memory] disabled: TASTE_MEMORY_PASSWORD missing')
        return
    path=Path(os.environ.get('TASTE_MEMORY_FILE','data/taste_memory.enc'))
    path.parent.mkdir(parents=True,exist_ok=True)
    import fcntl
    with open(str(path)+'.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        store=read_store(path,password)
        before=profile(store)
        index_path=Path('hashtag_index.json')
        added=0
        if index_path.is_file():
            added=seed_index(store,json.loads(index_path.read_text()),os.environ.get('MUSIC_CHANNEL_ID'))
        result=enrich(store,limit=int(os.environ.get('TASTE_TAG_LOOKUP_LIMIT','50')),
                      force=os.environ.get('TASTE_TAG_FORCE')=='1')
        if store['events']:
            write_store(path,password,store)
            if read_store(path,password)!=store:raise ValueError('Tag journal readback failed')
        after=profile(store)
        print('[tag_memory] '+json.dumps({'before_events':before['events'],'before_tagged':before['tagged'],
              'after_events':after['events'],'after_tagged':after['tagged'],'archive_seeded':added,**result}))

if __name__=='__main__':main()
