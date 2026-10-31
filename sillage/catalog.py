"""Provider boundary and normalized metadata. No scraping and no invented votes."""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote, urlparse
from urllib.error import HTTPError, URLError
import csv, json, math, os, re, unicodedata

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = 1

class CatalogError(Exception):
    def __init__(self, message, status=503): self.message, self.status = message, status

def utc_now(): return datetime.now(timezone.utc).isoformat()

def number(value, maximum=None):
    try: result = float(value)
    except (TypeError, ValueError): return None
    if not math.isfinite(result) or result < 0 or maximum is not None and result > maximum: return None
    return result

def image_url(value):
    if not isinstance(value, str): return None
    parsed = urlparse(value)
    return value if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password else None

def search_text(value):
    text = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode().lower()
    text = re.sub(r'[^a-z0-9]+', ' ', text).strip()
    aliases = {'ysl':'yves saint laurent', 'bdc':'bleu de chanel', 'dhi':'dior homme intense', 'dh':'dior homme', 'edp':'eau de parfum', 'edt':'eau de toilette'}
    return ' '.join(aliases.get(token, token) for token in text.split())

def fragrance_identity(metadata):
    """Duplicate upstream IDs need not mean different bottles. Keep explicit variants."""
    if not metadata.get('year')or not metadata.get('concentration'):
        return metadata['provider']+':'+metadata['external_id']
    brand=search_text(metadata['brand']).removeprefix('christian ')
    name=search_text(metadata['name'])
    for prefix in [brand,search_text(metadata['brand'])]:
        if name.startswith(prefix+' '):name=name[len(prefix)+1:]
    name=re.sub(r'\b(for men|for women|unisex)\b','',name)
    concentration=search_text(metadata['concentration'])
    name=name.replace(concentration,'').strip()
    return '|'.join([brand,re.sub(r'\s+',' ',name).strip(),str(metadata['year']),concentration,search_text(metadata.get('release_version',''))])

def fuzzy_fit(query, metadata):
    query = search_text(query)
    haystack = search_text(' '.join(str(metadata.get(k) or '') for k in ['brand','name','year','concentration']))
    if query in haystack: return 2 + len(query)/max(1,len(haystack))
    tokens = haystack.split()
    fits = [max((1 if token in word else SequenceMatcher(None,token,word).ratio() for word in tokens),default=0) for token in query.split()]
    if not fits or min(fits)<.68: return 0
    return sum(fits)/len(fits)

class FragranceDataProvider(ABC):
    name = 'unknown'
    @abstractmethod
    def search_fragrances(self, query): pass
    @abstractmethod
    def get_fragrance(self, external_id): pass
    @abstractmethod
    def status(self): pass
    def search_page(self,query,page=1,brand='',gender=''):
        records=self.search_fragrances(query)
        if brand:records=[m for m in records if search_text(brand) in search_text(m['brand'])]
        if gender:records=[m for m in records if str(m.get('gender')or'').lower() in gender.split(',')]
        return records if page==1 else [],False
    def get_fragrance_notes(self, external_id): return self.get_fragrance(external_id)['note_pyramid']
    def get_fragrance_accords(self, external_id): return self.get_fragrance(external_id)['main_accords']
    def get_community_ratings(self, external_id): return self.get_fragrance(external_id)['community_rating']
    def get_season_votes(self, external_id): return self.get_fragrance(external_id)['community'].get('seasons')
    def get_occasion_votes(self, external_id): return self.get_fragrance(external_id)['community'].get('occasions')
    def get_performance_data(self, external_id): return self.get_fragrance(external_id)['performance']

def empty_metadata(provider, external_id):
    return dict(schema_version=SCHEMA_VERSION, provider=provider, external_id=str(external_id), retrieved_at=utc_now(),
                brand='', name='', year=None, concentration=None, gender=None, image_url=None,source_url=None,
                community_rating=dict(value=None,count=None,scale=5), main_accords=[],
                note_pyramid=dict(top=[],middle=[],base=[],general=[],unresolved_count=0),
                performance={}, community={}, attributes={}, provenance={})

def derive_attributes(metadata):
    """Versioned conservative heuristics, explicitly marked inferred, never votes."""
    a, provenance = metadata['attributes'], metadata['provenance']
    accords={v['name'].lower():v.get('value') for v in metadata['main_accords'] if v.get('value') is not None}
    maps={'sweetness':['sweet'],'woodiness':['woody'],'citrus':['citrus'],'aquatic':['aquatic','marine'],
          'floral':['floral','white floral'],'powderiness':['powdery'],'spiciness':['warm spicy','fresh spicy'],'richness':['amber','oud','tobacco','leather']}
    for attribute, names in maps.items():
        matches=[accords[n] for n in names if n in accords]
        if matches and attribute not in a: a[attribute]=round(max(matches))
    fresh=[accords[n] for n in ['citrus','fresh','fresh spicy','aquatic','marine','green'] if n in accords]
    warm=[accords[n] for n in ['amber','warm spicy','vanilla','sweet','oud','tobacco'] if n in accords]
    if fresh or warm:
        if 'freshness' not in a: a['freshness']=round(max(fresh)) if fresh else round(100-max(warm)*.8)
        if 'warmth' not in a: a['warmth']=round(max(warm)) if warm else round(100-max(fresh)*.8)
    for attribute in a: provenance.setdefault('attributes.'+attribute,dict(source='inferred',method='accord/performance mapping v1'))
    metadata['identity']=fragrance_identity(metadata)
    return metadata

def collection_data(metadata):
    """Engine-facing normalized fields; the complete source snapshot is retained."""
    longevity=metadata.get('performance',{}).get('longevity',{}).get('estimated_hours')
    return dict(brand=metadata['brand'], name=metadata['name'], concentration=metadata.get('concentration') or '',
                family=metadata.get('family') or '', accords=', '.join(a['name'] for a in metadata['main_accords']),
                top_notes=', '.join(n['name'] for n in metadata['note_pyramid']['top']),
                middle_notes=', '.join(n['name'] for n in metadata['note_pyramid']['middle']),
                base_notes=', '.join(n['name'] for n in metadata['note_pyramid']['base']),
                notes='', tags='', attributes=metadata['attributes'].copy(),longevity=longevity,
                rating=None,bottle_size=None,favorite=False,occasions=[],dayparts=[],seasons=[],
                source=metadata['provider'],metadata=metadata,overrides=[],provenance=metadata['provenance'].copy())

def fragdb_votes(value, prefix):
    values, counts = {}, {}
    for item in (value or '').split(';'):
        parts=item.split(':')
        if len(parts)!=3: continue
        label=parts[0].removeprefix(prefix).replace('fall','autumn')
        count,percent=number(parts[1]),number(parts[2],100)
        if percent is not None: values[label]=percent/100
        if count is not None: counts[label]=int(count)
    # Multi-select counts are not the number of distinct respondents.
    return dict(values=values,counts=counts,sample_count=None,source='community',normalization='provider percentages / 100')

LONGEVITY={'very weak':1,'poor':1,'weak':2.5,'moderate':5.5,'long lasting':10,'very long lasting':14,'eternal':14}
PROJECTION={'intimate':15,'soft':30,'moderate':50,'strong':80,'enormous':100}

def weighted_estimate(distribution, mapping):
    counts=distribution.get('counts',{})
    pairs=[(mapping[k.replace('_',' ')],v) for k,v in counts.items() if k.replace('_',' ') in mapping]
    return round(sum(x*n for x,n in pairs)/sum(n for _,n in pairs),2) if pairs and sum(n for _,n in pairs)>0 else None

def normalize_fragdb(row, notes, accords, provider):
    m=empty_metadata(provider,row['pid']);m.update(brand=row['brand'].split(';')[0],name=row['name'],year=int(row['year']) if row.get('year','').isdigit() else None,
        concentration=row.get('concentration') or None,gender={'gender_for_men':'Men','gender_for_women':'Women','gender_for_women_and_men':'Unisex'}.get(row.get('gender')),image_url=image_url(row.get('main_photo')),source_url=image_url(row.get('url')))
    m['release_version']=row.get('release_version')or row.get('reformulation')or None
    for field in ['brand','name','year','concentration','gender','image_url']:m['provenance'][field]=dict(source='provider',provider=provider)
    rating=(row.get('rating') or '').split(';');m['community_rating']=dict(value=number(rating[0],5),count=int(number(rating[1]) or 0) if len(rating)>1 else None,scale=5)
    m['provenance']['community_rating']=dict(source='community',provider=provider)
    unresolved_accords=0
    for pair in (row.get('accords') or '').split(';'):
        key,_,value=pair.partition(':')
        if key in accords:m['main_accords'].append(dict(name=accords[key],value=number(value,100),source='community'))
        elif key:unresolved_accords+=1
    m['unresolved_accords']=unresolved_accords
    for layer,body in re.findall(r'(top|middle|base|notes)\(([^)]*)\)',row.get('notes_pyramid','')):
        for note in body.split(';'):
            key=note.split(',')[0]
            if key in notes:m['note_pyramid']['general' if layer=='notes' else layer].append(dict(name=notes[key],source='provider'))
            elif key:m['note_pyramid']['unresolved_count']+=1
    for own,field,prefix in [('seasons','season','season_'),('dayparts','time_of_day','season_'),('longevity','longevity','longevity_'),('projection','sillage','sillage_'),('gender','gender_votes','gvotes_'),('value','price_value','price_')]:
        m['community'][own]=fragdb_votes(row.get(field,''),prefix)
    for key,mapping in [('longevity',LONGEVITY),('projection',PROJECTION)]:
        dist=m['community'][key]; estimate=weighted_estimate(dist,mapping)
        winner=max(dist['counts'],key=dist['counts'].get).replace('_',' ') if dist['counts'] else None
        m['performance'][key]=dict(label=winner,source='community',sample_count=sum(dist['counts'].values()) if dist['counts'] else None)
        if key=='longevity':m['performance'][key]['estimated_hours']=estimate
        elif estimate is not None:m['attributes']['projection']=round(estimate)
        m['provenance'][key if key=='longevity' else 'attributes.projection']=dict(source='inferred',method='community vote-weighted category estimate v1')
    # The documented FragDB v5 export has no occasion votes. Keep them absent.
    if row.get('occasion'):m['community']['occasions']=fragdb_votes(row['occasion'],'occasion_')
    return derive_attributes(m)

class LocalFragranceProvider(FragranceDataProvider):
    def __init__(self, folder, sample=False):
        self.folder, self.sample = Path(folder),sample
        self.name='fragdb-sample' if sample else 'fragdb'
        self._signature=None;self._records={}
    def load(self):
        source=self.folder/'fragrances.csv'
        if not source.exists():raise CatalogError('The configured fragrance database is unavailable. Check the server catalog path.')
        files=[self.folder/name for name in ['fragrances.csv','notes.csv','accords.csv']]
        signature=tuple(p.stat().st_mtime_ns if p.exists() else None for p in files)
        if signature==self._signature:return
        def rows(file):
            if not file.exists():return []
            with file.open(encoding='utf-8-sig',newline='')as stream:return list(csv.DictReader(stream,delimiter='|'))
        notes={r['id']:r['name'] for r in rows(files[1])};accords={r['id']:r['name'] for r in rows(files[2])}
        try:records={str(r['pid']):normalize_fragdb(r,notes,accords,self.name) for r in rows(source)}
        except (KeyError,ValueError,TypeError)as exc:raise CatalogError('The configured FragDB export has an invalid schema.')from exc
        self._records,self._signature=records,signature
    def search_fragrances(self,query):
        self.load();matches=[(fuzzy_fit(query,m),m)for m in self._records.values()]
        return [m for fit,m in sorted(matches,key=lambda pair:(-pair[0],pair[1]['name']))if fit>=.72][:10]
    def get_fragrance(self,external_id):
        self.load()
        if str(external_id)not in self._records:raise CatalogError('That fragrance is no longer available in this catalog.',404)
        # File refreshes are noticed on each lookup; retrieval timestamp is real.
        return {**self._records[str(external_id)],'retrieved_at':utc_now()}
    def status(self):
        self.load()
        return dict(name=self.name,ready=True,count=len(self._records),evaluation=self.sample,
                    label=f'FragDB evaluation catalog · {len(self._records)} fragrances' if self.sample else 'Licensed local fragrance catalog',
                    attribution_url='https://fragdb.net',license_url='https://creativecommons.org/licenses/by-nc/4.0/' if self.sample else None)

def fragella_ranking(raw):
    """Rank scores are relative provider scores, never fabricated community votes."""
    entries=raw if isinstance(raw,list) else []
    raw_values={}
    for item in entries:
        if not isinstance(item,dict):continue
        name=str(item.get('name','')).lower().replace('fall','autumn')
        value=next((number(item[k])for k in ['score','value','Score','ranking']if k in item),None)
        if name and value is not None:raw_values[name]=value
    maximum=max(raw_values.values(),default=0)
    return dict(values={k:v/maximum if maximum else 0 for k,v in raw_values.items()},raw_values=raw_values,
                counts={},sample_count=None,source='provider',normalization='relative to highest provider rank; not vote percentages')

def normalize_fragella(row):
    if not isinstance(row,dict)or not row.get('_id')or not row.get('Name')or not row.get('Brand'):raise CatalogError('The fragrance provider returned an incomplete record.')
    m=empty_metadata('fragella',row['_id']);m.update(brand=str(row['Brand']),name=str(row['Name']),year=int(row['Year'])if str(row.get('Year','')).isdigit()else None,
        concentration=row.get('OilType')or None,gender=row.get('Gender')or None,image_url=image_url(row.get('Image URL Transparent'))or image_url(row.get('Image URL')))
    m['release_version']=row.get('Release Version')or None
    for field in ['brand','name','year','concentration','gender','image_url']:m['provenance'][field]=dict(source='provider',provider='fragella')
    # The documented API doesn't expose vote counts. Do not infer them from popularity.
    m['community_rating']=dict(value=number(row.get('rating'),5),count=None,scale=5,method='provider Bayesian rating')
    m['provider_confidence']=row.get('Confidence')
    if row.get('Price Value'):m['community']['value']=dict(label=row['Price Value'],source='provider',sample_count=None,values={},counts={})
    for layer in ['Top','Middle','Base']:
        for note in (row.get('Notes')or {}).get(layer,[]):
            name=note.get('name')if isinstance(note,dict)else note
            if name:m['note_pyramid'][layer.lower()].append(dict(name=str(name),source='provider'))
    m['note_pyramid']['general']=[dict(name=str(n),source='provider')for n in row.get('General Notes',[])if isinstance(n,str)]
    strength={'Dominant':100,'Prominent':75,'Moderate':50,'Subtle':25}
    for accord in row.get('Main Accords',[]):
        raw=(row.get('Main Accords Percentage')or {}).get(accord)
        value=number(raw,100)
        inferred=value is None and raw in strength
        m['main_accords'].append(dict(name=str(accord),value=strength[raw]if inferred else value,source='inferred'if inferred else 'provider',descriptor=raw))
    for key,field,mapping in [('longevity','Longevity',LONGEVITY),('projection','Sillage',PROJECTION)]:
        label=row.get(field);estimate=mapping.get(str(label).lower())
        m['performance'][key]=dict(label=label,source='provider',sample_count=None)
        if key=='longevity':m['performance'][key]['estimated_hours']=estimate
        elif estimate is not None:m['attributes']['projection']=estimate
        m['provenance'][key if key=='longevity'else'attributes.projection']=dict(source='inferred',method='provider descriptor midpoint v1')
    for key,field in [('seasons','Season Ranking'),('occasions','Occasion Ranking')]:m['community'][key]=fragella_ranking(row.get(field))
    return derive_attributes(m)

class FragellaProvider(FragranceDataProvider):
    name='fragella'
    def __init__(self,key):self.key=key
    def fetch(self,path,params=None):
        if not self.key:raise CatalogError('Fragella is not configured. Set FRAGELLA_API_KEY on the server.')
        url='https://api.fragella.com/api/v1/'+path+('?' +urlencode(params)if params else '')
        try:
            with urlopen(Request(url,headers={'x-api-key':self.key,'Accept':'application/json','User-Agent':'Sillage/0.2'}),timeout=8)as response:raw=json.loads(response.read(4*1024*1024))
            return raw
        except HTTPError as error:
            if error.code in [401,403]:raise CatalogError('The fragrance provider rejected its server credential. Check the configured API key.')from None
            if error.code==429:raise CatalogError('The fragrance provider is temporarily rate limited. Try again shortly.',429)from None
            if error.code==404:raise CatalogError('This fragrance is no longer available from the provider.',404)from None
            raise CatalogError('The fragrance provider is unavailable. Try again shortly.')from None
        except (URLError,TimeoutError,ValueError,OSError):raise CatalogError('Could not reach the fragrance provider. Try again shortly.')from None
    def search_fragrances(self,query):
        raw=self.fetch('fragrances',dict(search=search_text(query),limit=10))
        if isinstance(raw,dict):raw=raw.get('data',[])
        if not isinstance(raw,list):raise CatalogError('The fragrance provider returned an invalid search response.')
        return [normalize_fragella(r)for r in raw]
    def search_page(self,query,page=1,brand='',gender=''):
        params=dict(search=search_text(query),limit=10,page=page)
        if brand:params['brand']=brand
        if gender:params['gender']=gender
        raw=self.fetch('fragrances',params)
        more=isinstance(raw,dict) and bool(raw.get('pagination',{}).get('has_more')) and page<2
        rows=raw.get('data',[])if isinstance(raw,dict)else raw
        if not isinstance(rows,list):raise CatalogError('The fragrance provider returned an invalid search response.')
        return [normalize_fragella(r)for r in rows],more
    def get_fragrance(self,external_id):
        raw=self.fetch('fragrances/'+quote(str(external_id),safe=''))
        if isinstance(raw,list):raw=raw[0]if raw else None
        return normalize_fragella(raw)
    def status(self):return dict(name=self.name,ready=bool(self.key),evaluation=False,label='Fragella fragrance catalog',attribution_url='https://api.fragella.com',license_url='https://api.fragella.com/terms-of-use.html')

def configured_provider():
    name=os.environ.get('SILLAGE_FRAGRANCE_PROVIDER','').lower()
    folder=os.environ.get('SILLAGE_FRAGDB_PATH')
    if name=='fragella'or(not name and os.environ.get('FRAGELLA_API_KEY')):return FragellaProvider(os.environ.get('FRAGELLA_API_KEY'))
    if name=='fragdb'or folder:
        if not folder:raise CatalogError('Set SILLAGE_FRAGDB_PATH to your licensed FragDB export directory.')
        return LocalFragranceProvider(folder)
    if name not in ['', 'sample']:raise CatalogError('Unknown fragrance provider. Configure fragella, fragdb, or sample.')
    return LocalFragranceProvider(ROOT/'third_party/fragdb_sample',sample=True)

def merge_metadata(original,metadata):
    """Refresh provider priors while retaining every explicit user override."""
    result=collection_data(metadata);overrides=set(original.get('overrides',[]))
    for key in ['rating','bottle_size','favorite','notes','tags','personal_longevity','limits']:result[key]=original.get(key,result.get(key))
    result['limits']=original.get('limits') or {}
    for key in overrides:
        if key.startswith('attributes.'):
            attr=key.split('.',1)[1]
            if attr in original.get('attributes',{}):result['attributes'][attr]=original['attributes'][attr]
            else:result['attributes'].pop(attr,None)
        elif key in original:result[key]=original[key]
        result['provenance'][key]=dict(source='user')
    result['overrides']=sorted(overrides)
    return result
