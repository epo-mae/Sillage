"""External input adapters. No calendar or fragrance data sent to third parties."""
import json, os, time, threading
from urllib.request import urlopen
from urllib.parse import urlencode
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from icalendar import Calendar

_cache, _lock = {}, threading.Lock()

def weather_for(preferences):
    if not preferences.get('weather_enabled',True) or preferences.get('latitude') is None: return None,None
    params = dict(latitude=preferences['latitude'],longitude=preferences['longitude'],timezone=preferences['timezone'],forecast_days=7,
                  current='temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,wind_speed_10m,weather_code',
                  hourly='temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,wind_speed_10m')
    key = urlencode(params)
    with _lock:
        cached = _cache.get(key)
    if cached and time.time()-cached[0]<900: return cached[1],None
    api_key = os.environ.get('OPEN_METEO_API_KEY')
    host = 'customer-api.open-meteo.com' if api_key else 'api.open-meteo.com'
    if api_key: params['apikey']=api_key
    try:
        with urlopen(f'https://{host}/v1/forecast?{urlencode(params)}',timeout=8) as response: raw=json.load(response)
        zone=ZoneInfo(preferences['timezone'])
        current=raw['current']; hourly=raw['hourly']
        result=dict(source='Open-Meteo',fetched_at=datetime.now(zone).isoformat(),current=dict(temperature=current['temperature_2m'],feels_like=current['apparent_temperature'],humidity=current['relative_humidity_2m'],precipitation=current['precipitation'],wind=current['wind_speed_10m']),
                    hourly=[dict(time=datetime.fromisoformat(t).replace(tzinfo=zone).isoformat(),temperature=hourly['temperature_2m'][i],feels_like=hourly['apparent_temperature'][i],humidity=hourly['relative_humidity_2m'][i],precipitation=hourly['precipitation'][i],wind=hourly['wind_speed_10m'][i]) for i,t in enumerate(hourly['time'])])
        with _lock: _cache[key]=(time.time(),result)
        return result,None
    except Exception:
        return None,'Weather is unavailable. Ranking uses your remaining context; try refreshing later.'

def import_calendar(text, timezone):
    zone=ZoneInfo(timezone)
    def normalize(value):
        if isinstance(value,datetime): return value.replace(tzinfo=zone) if value.tzinfo is None else value.astimezone(zone)
        return datetime.combine(value,datetime.min.time(),zone)
    result=[]
    try: calendar=Calendar.from_ical(text)
    except Exception as exc: raise ValueError('This file is not a valid iCalendar export.') from exc
    for event in calendar.walk('VEVENT'):
        if event.get('RRULE'): raise ValueError('Export expanded occurrences first. Recurring rules are not supported in this MVP.')
        if str(event.get('STATUS',''))=='CANCELLED': continue
        if not event.get('DTSTART'): continue
        start=normalize(event.decoded('DTSTART'))
        end=normalize(event.decoded('DTEND')) if event.get('DTEND') else start+(event.decoded('DURATION') if event.get('DURATION') else timedelta(hours=1))
        if end<=start: raise ValueError('Calendar event end must follow its start.')
        result.append(dict(title=str(event.get('SUMMARY','Untitled event'))[:200],location=str(event.get('LOCATION',''))[:300],start=start.isoformat(),end=end.isoformat(),source='calendar import'))
        if len(result)>1000: raise ValueError('Import at most 1,000 events at a time.')
    return result
