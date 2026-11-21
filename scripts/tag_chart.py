"""Private aggregate-only JPEG charts. No model, raw names or identifiers."""
import os
from pathlib import Path
from tag_profile import profile

def render_jpg(store, output):
    from PIL import Image, ImageDraw, ImageFont
    summary=profile(store)
    image=Image.new('RGB',(1600,1060),'#0c1424')
    draw=ImageDraw.Draw(image)
    def font(size):
        for path in ('/System/Library/Fonts/Supplemental/Arial.ttf',
                     '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
            if Path(path).is_file():
                return ImageFont.truetype(path,size)
        return ImageFont.load_default(size=size)
    def text(x,y,value,size=24,color='#e5edf8'):
        draw.text((x,y),str(value),font=font(size),fill=color)
    def panel(box):
        draw.rounded_rectangle(box,radius=20,fill='#152137')
    total=summary['events']
    direct=sum('vibe_admin' in event.get('sources',[]) for event in store['events'].values())
    timed=sum(event.get('sent_at_utc') is not None for event in store['events'].values())
    text(60,42,'MUSIC SELECTION SNAPSHOT',38)
    text(60,96,'Local weighted-tag analysis | Asia/Tehran | No AI inference',23,'#94a9c4')
    for i,(label,value) in enumerate([('RECORDED CHOICES',total),('DIRECT ADMIN CHOICES',direct),('WITH KNOWN SEND TIME',timed),('WITH RECOGNIZED TAGS',summary['tagged'])]):
        x=60+i*375
        panel((x,155,x+350,285))
        text(x+22,175,label,16,'#a5b5cf')
        text(x+22,212,value,42,'#69ddd0')
    panel((60,320,790,875))
    text(86,344,'WEIGHTED TAGS',25)
    text(86,385,'Direct selection = 3 | Other observation = 1',17,'#a5b5cf')
    tags=sorted(summary['weighted_tags'].items(),key=lambda item:(-item[1],item[0]))[:10]
    if not tags:
        text(100,520,'No recognized tags yet',30,'#f5c76b')
        text(100,575,'Missing tags stay UNKNOWN.',22)
        text(100,620,'No happiness/sadness score is inferred.',19,'#a5b5cf')
    else:
        maximum=max(score for _,score in tags)
        for i,(tag,score) in enumerate(tags):
            y=435+i*40
            text(86,y,tag,19)
            draw.rounded_rectangle((300,y+4,300+360*score/maximum,y+25),radius=5,fill='#69ddd0')
            text(685,y,score,19)
    panel((820,320,1540,875))
    text(846,344,'CHOICES BY SEND-TIME BUCKET',25)
    text(846,385,'Unweighted event counts, not weighted tag totals',17,'#a5b5cf')
    buckets=summary['time_buckets']
    maximum=max((group['events'] for group in buckets.values()),default=0) or 1
    labels={'night':'Night 00-06','morning':'Morning 06-12','afternoon':'Afternoon 12-18','evening':'Evening 18-24','unknown':'Unknown time'}
    for i,(name,group) in enumerate(buckets.items()):
        y=445+i*76
        text(846,y,labels[name],19)
        width=400*group['events']/maximum
        if width:
            draw.rounded_rectangle((846,y+30,846+width,y+49),radius=5,fill='#90abef' if name!='unknown' else '#758197')
        text(1280,y+23,group['events'],22)
    text(60,914,f"Coverage: {summary['tagged']}/{total} choices have recognized tags. Repeated observations of one post are deduplicated.",22)
    text(60,958,'Musical tags and selection time do not measure your personal mood or psychological wellbeing.',22,'#f5c76b')
    text(60,1000,'Source: encrypted local journal | Output excludes track names, artist names, captions and account identifiers.',18,'#94a9c4')
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'wb') as stream:
        image.save(stream,format='JPEG',quality=95,subsampling=0)
    os.chmod(output,0o600)
