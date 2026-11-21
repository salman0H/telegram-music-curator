"""Aggregate fuzzy time-membership and explicit-affect JPEG output; no mood guesses."""
import json
import os
from pathlib import Path
from fuzzy_mood import time_memberships,summarize,infer

def fuzzy_profile(store):
    events=list(store['events'].values())
    weights={name:0.0 for name in ('night','morning','afternoon','evening')}
    total_weight=0
    timed=0
    points=[]
    for event in events:
        weight=event.get('preference_weight',1)
        memberships=time_memberships(event.get('local_time'))
        if memberships:
            timed+=1
            total_weight+=weight
            for name,value in memberships.items():weights[name]+=weight*value
        result=infer(event.get('music_mood',{}))
        if result['status']=='estimated':
            points.append({'valence':result['valence_score'],'energy':result['energy_score'],'weight':weight})
    return {'method':'mamdani-music-v1 + circular-time-v1','events':len(events),'timed_events':timed,
            'weighted_time_membership':{name:value/total_weight if total_weight else None for name,value in weights.items()},
            'time_weight_total':total_weight,'affect':summarize(events),'affect_points':points,
            'interpretation':'Musical/tag memberships, not personal wellbeing or calibrated probabilities.'}

def export_json(store,path):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(fuzzy_profile(store),stream,indent=2)

def render_jpg(store,path):
    from PIL import Image,ImageDraw,ImageFont
    data=fuzzy_profile(store)
    image=Image.new('RGB',(1600,1100),'#0c1424')
    draw=ImageDraw.Draw(image)
    def font(size):
        for name in ('/System/Library/Fonts/Supplemental/Arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
            if Path(name).is_file():return ImageFont.truetype(name,size)
        return ImageFont.load_default(size=size)
    def text(x,y,value,size=23,color='#e5edf8'):draw.text((x,y),str(value),font=font(size),fill=color)
    def panel(box):draw.rounded_rectangle(box,radius=20,fill='#152137')
    text(60,42,'FUZZY MUSIC & TIME PROFILE',38)
    text(60,100,'Actual observed data | Offline rules | No agent | Membership degrees are not probabilities',22,'#94a9c4')
    panel((60,155,790,865));panel((820,155,1540,865))
    text(85,180,'FUZZY SEND-TIME MEMBERSHIP',26)
    text(85,225,f"Time coverage: {data['timed_events']}/{data['events']} events",22)
    text(85,265,'Circular overlapping windows; source weights 3 / 1',20,'#a5b5cf')
    colors=['#a998ed','#e9c56e','#6fd3ba','#79a7ef']
    for i,(name,value) in enumerate(data['weighted_time_membership'].items()):
        y=345+i*100
        text(85,y,name.title(),23)
        draw.rounded_rectangle((85,y+38,650,y+62),radius=5,fill='#24334b')
        if value:
            draw.rounded_rectangle((85,y+38,85+565*value,y+62),radius=5,fill=colors[i])
        text(680,y+29,'N/A' if value is None else f'{value:.3f}',22)
    text(85,775,'Bars show weighted mean membership, not event counts.',18,'#a5b5cf')
    text(845,180,'EXPLICIT MUSICAL AFFECT',26)
    used=data['affect']['classified']
    text(845,225,f"Valence + energy coverage: {used}/{data['events']} events",22)
    text(845,265,'Mamdani min / max / centroid',20,'#a5b5cf')
    x0,y0,x1,y1=915,350,1460,730
    draw.rectangle((x0,y0,x1,y1),outline='#647793',width=2)
    draw.line(((x0+x1)/2,y0,(x0+x1)/2,y1),fill='#3b4d67',width=1)
    draw.line((x0,(y0+y1)/2,x1,(y0+y1)/2),fill='#3b4d67',width=1)
    text(x0,750,'Sad / negative',18);text(x1-150,750,'Happy / positive',18)
    text(845,y0-30,'High energy',18);text(845,y1+45,'Low energy',18)
    if points:=data['affect_points']:
        for point in points:
            x=x0+(point['valence']+1)/2*(x1-x0)
            y=y1-point['energy']*(y1-y0)
            radius=5+point['weight']*2
            draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill='#6fd3ba')
    else:
        text(980,480,'Insufficient explicit tags',25,'#f5c76b')
        text(980,530,'No affect points invented.',21)
    text(60,910,'Time is used only for grouping. Genre tags do not establish sadness, happiness or psychological state.',22,'#f5c76b')
    text(60,955,'Emotion panel needs BOTH an explicit valence tag (sad/happy/neutral) and energy tag (calm/energetic).',21)
    text(60,1000,'Missing timestamps and missing affect tags remain unknown. Raw recording names and identifiers are excluded.',20,'#a5b5cf')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'wb') as stream:image.save(stream,format='JPEG',quality=95,subsampling=0)
