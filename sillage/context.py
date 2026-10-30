from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def classify(title):
    title = title.lower()
    for words, occasion, environment in [(['flight','plane'],'travel','confined'),(['meeting','office','interview','work','class'],'work','confined'),(['wedding','gala','formal'],'formal','indoor'),(['gym','run','hike','park','outdoor'],'outdoor','outdoor'),(['date'],'date','indoor'),(['dinner','restaurant'],'dinner','indoor'),(['party','club'],'party','indoor')]:
        if any(word in title for word in words): return occasion,environment
    return 'casual','unknown'

def build_context(preferences, weather=None, events=None, now=None, mode='now', event_id=None):
    zone = ZoneInfo(preferences.get('timezone','Pacific/Auckland'))
    now = (now or datetime.now(zone)).astimezone(zone)
    if mode=='tonight':
        tonight = now.replace(hour=18,minute=0,second=0,microsecond=0)
        now = max(now,tonight)
    nearby = []
    for event in events or []:
        start,end = datetime.fromisoformat(event['start']),datetime.fromisoformat(event['end'])
        if end>now and start<now+timedelta(hours=8): nearby.append(event)
    if mode=='event':
        selected = next((e for e in events or [] if str(e['id'])==str(event_id)),None)
        if not selected: raise ValueError('Select an available calendar event.')
        now = datetime.fromisoformat(selected['start']).astimezone(zone)
        nearby = [selected]
    end = max([now+timedelta(hours=4)]+[datetime.fromisoformat(e['end']) for e in nearby])
    end = min(end,now+timedelta(hours=12))
    relevant = min(nearby,key=lambda e:e['start']) if nearby else None
    occasion,environment = classify(relevant['title']) if relevant else ('casual','unknown')
    occasion = preferences.get('occasion','automatic') if preferences.get('occasion','automatic')!='automatic' else occasion
    if occasion in ['work','interview','travel']: environment='confined'
    if occasion=='outdoor': environment='outdoor'
    if occasion in ['dinner','date','formal','party','wedding']: environment='indoor'
    month = now.month
    season = ['winter','spring','summer','autumn'][(month%12)//3]
    latitude = preferences.get('latitude')
    if latitude is None: season=None
    elif latitude<0: season={'winter':'summer','summer':'winter','spring':'autumn','autumn':'spring'}[season]
    hours = [h for h in (weather or {}).get('hourly',[]) if now <= datetime.fromisoformat(h['time']) < end]
    current = (weather or {}).get('current',{}) if mode=='now' else {}
    temps = [h['temperature'] for h in hours if h.get('temperature') is not None]
    if current.get('temperature') is not None: temps.insert(0,current['temperature'])
    humidity = [h['humidity'] for h in hours if h.get('humidity') is not None]
    def horizon_value(key):
        values=[h[key] for h in hours if h.get(key) is not None]
        return (max(values) if key=='precipitation' else sum(values)/len(values)) if values else current.get(key)
    return dict(now=now.isoformat(),end=end.isoformat(),duration=round((end-now).total_seconds()/3600,1),
                daypart='night' if now.hour<5 or now.hour>=22 else 'morning' if now.hour<12 else 'afternoon' if now.hour<17 else 'evening',
                season=season,occasion=occasion,environment=environment,events=nearby,
                context_certainty=.8 if (relevant and environment!='unknown') or preferences.get('occasion','automatic')!='automatic' else .4,
                location=preferences.get('location','Location not set'),weather=weather if temps else None,
                forecast=hours,temperature=sum(temps)/len(temps) if temps else None,
                temperature_range=[min(temps),max(temps)] if temps else None,
                humidity=sum(humidity)/len(humidity) if humidity else current.get('humidity'),
                feels_like=horizon_value('feels_like'),wind=horizon_value('wind'),precipitation=horizon_value('precipitation'))
