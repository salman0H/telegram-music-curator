"""Non-AI catalog genre enrichment with recording identity checks."""
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from tag_profile import canonical

def normalize(value):
    return re.sub(r'[^\w]+','',unicodedata.normalize('NFKC',value or '').casefold()).replace('_','')

def genres_to_tags(genres):
    # These are descriptive genre aliases, never mood inference rules.
    aliases={'r&b/soul':['rnb','soul'],'hip-hop/rap':['hiphop','rap'],
             'singer/songwriter':['singersongwriter'],'dance':['dance'],
             'new age':['newage'],'children’s music':['children'],
             'children\'s music':['children'],'alternative':['alternative']}
    values=[]
    for genre in genres or []:
        if not isinstance(genre,str):continue
        values.extend(aliases.get(genre.casefold().strip(),[genre]))
    return canonical(values)

def lookup(artist,title):
    if not artist or not title or normalize(artist) in ('unknown','unknownartist') or normalize(title) in ('unknown','unknowntitle'):
        return {'status':'missing_identity','tags':[]}
    params=urllib.parse.urlencode({'term':f'{artist} {title}','entity':'song','media':'music','country':'US','limit':10})
    request=urllib.request.Request('https://itunes.apple.com/search?'+params,headers={'User-Agent':'LocalMusicTagMemory/1.0'})
    try:
        with urllib.request.urlopen(request,timeout=12) as response:
            results=json.load(response).get('results',[])
        for track in results:
            if normalize(track.get('artistName'))!=normalize(artist) or normalize(track.get('trackName'))!=normalize(title):
                continue
            genre=track.get('primaryGenreName')
            tags=genres_to_tags([genre] if genre else [])
            return {'status':'matched' if tags else 'unmapped_genre','tags':tags,
                    'provider':'itunes','recording_id':track.get('trackId')}
        return {'status':'no_exact_match','tags':[],'provider':'itunes'}
    except Exception as error:
        return {'status':'provider_error','tags':[],'provider':'itunes','error_type':type(error).__name__}
