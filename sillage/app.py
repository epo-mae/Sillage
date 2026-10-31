import json, os, secrets, sqlite3, time, threading, math, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from functools import wraps
from contextlib import closing
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from flask import Flask, request, jsonify, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from .engine import rank, ATTRIBUTES, WEIGHTS
from .context import build_context
from .providers import weather_for, import_calendar
from .catalog import configured_provider, CatalogError, collection_data, merge_metadata, utc_now

ROOT=Path(__file__).resolve().parent.parent
DEFAULTS=dict(timezone='Pacific/Auckland',location='',latitude=None,longitude=None,weather_enabled=True,calendar_enabled=True,application=True,projection=50,variety=1,favorite_bias=4,occasion='automatic',units='celsius',weights=WEIGHTS.copy())
OCCASIONS=['casual','work','dinner','date','formal','wedding','interview','party','outdoor','travel']

def create_app(database=None, testing=False, fragrance_provider=None):
    app=Flask(__name__,static_folder=str(ROOT/'static'),static_url_path='')
    # Tie each page load to the assets shipped with this deployment. Browsers and
    # reverse proxies may retain unversioned JavaScript long after a rebuild.
    index_html=(ROOT/'static/index.html').read_text(encoding='utf-8')
    for asset in ['app.js','catalog.js','atmosphere.js','style.css','catalog.css','atmosphere.css','mark.svg']:
        version=hashlib.sha256((ROOT/'static'/asset).read_bytes()).hexdigest()[:16]
        index_html=index_html.replace(f'"/{asset}"',f'"/{asset}?v={version}"')
    data_dir=ROOT/'data'; data_dir.mkdir(exist_ok=True)
    secret=os.environ.get('SILLAGE_SECRET_KEY')
    if not secret:
        keyfile=data_dir/'session.key'
        if not keyfile.exists(): keyfile.write_text(secrets.token_hex(32))
        secret=keyfile.read_text().strip()
    app.config.update(SECRET_KEY=secret,DATABASE=str(database or data_dir/'sillage.db'),TESTING=testing,MAX_CONTENT_LENGTH=1024*1024,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',SESSION_COOKIE_SECURE=os.environ.get('SILLAGE_SECURE_COOKIE')=='1',PERMANENT_SESSION_LIFETIME=timedelta(days=7))
    with closing(sqlite3.connect(app.config['DATABASE'])) as connection:
        connection.executescript((ROOT/'sillage/schema.sql').read_text())
        connection.execute('PRAGMA journal_mode=WAL')
        connection.commit()
    attempts={}; attempts_lock=threading.Lock()
    catalog_provider=fragrance_provider or configured_provider()
    search_cache={}; search_more={}; catalog_lock=threading.Lock()
    metadata_ttl=int(os.environ.get('SILLAGE_METADATA_TTL_DAYS','7'))*86400

    def db():
        if 'db' not in g:
            g.db=sqlite3.connect(app.config['DATABASE'],timeout=10)
            g.db.row_factory=sqlite3.Row
            g.db.execute('PRAGMA foreign_keys=ON')
        return g.db
    @app.teardown_appcontext
    def close(_):
        connection=g.pop('db',None)
        if connection: connection.close()
    def write(query,args=()):
        result=db().execute(query,args); db().commit(); return result.lastrowid
    def now(): return datetime.now(timezone.utc).isoformat()
    def body():
        value=request.get_json(silent=True)
        if not isinstance(value,dict): raise ValueError('Expected a JSON object.')
        return value
    def user(): return db().execute('SELECT * FROM users WHERE id=? AND id=(SELECT MIN(id) FROM users)',(session.get('user_id'),)).fetchone()
    def profile(row): return dict(id=row['id'],name=row['name'],email=row['email'],preferences=json.loads(row['preferences']))
    def owned(table,identifier):
        row=db().execute(f'SELECT * FROM {table} WHERE id=? AND user_id=?',(identifier,session['user_id'])).fetchone()
        if not row: raise ValueError('Record not found.')
        return row
    def authenticated(fn):
        @wraps(fn)
        def inner(*args,**kwargs):
            if not user(): return jsonify(error='Please sign in.'),401
            return fn(*args,**kwargs)
        return inner
    @app.before_request
    def csrf():
        if request.path.startswith('/api/') and request.method not in ['GET','HEAD','OPTIONS']:
            if not session.get('csrf') or not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),session['csrf']):
                return jsonify(error='Session expired. Reload and try again.'),403
    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data: https:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        if request.path.startswith('/api/'): response.headers['Cache-Control']='no-store'
        return response
    @app.errorhandler(ValueError)
    def invalid(error): return jsonify(error=str(error)),400
    @app.errorhandler(CatalogError)
    def catalog_error(error): return jsonify(error=error.message),error.status
    @app.errorhandler(413)
    def too_large(_): return jsonify(error='Upload is too large. Maximum size is 1 MB.'),413
    @app.errorhandler(sqlite3.IntegrityError)
    def conflict(_): return jsonify(error='This record already exists. Refresh to see the saved result.'),409
    @app.errorhandler(500)
    def failed(_): return jsonify(error='Something went wrong. Your saved data is safe; try again.'),500
    @app.get('/')
    @app.get('/index.html')
    def index():
        response=app.make_response(index_html)
        response.headers['Cache-Control']='no-store'
        return response
    @app.get('/api/session')
    def get_session():
        if 'csrf' not in session: session['csrf']=secrets.token_hex(24)
        return jsonify(user=profile(user()) if user() else None,csrf=session['csrf'],defaults=DEFAULTS,registration_open=not db().execute('SELECT 1 FROM users LIMIT 1').fetchone())
    def rate_limit():
        key=request.remote_addr
        with attempts_lock:
            values=[t for t in attempts.get(key,[]) if time.time()-t<300]
            if len(values)>=15: raise ValueError('Too many attempts. Try again in five minutes.')
            attempts[key]=values+[time.time()]
            if len(attempts)>10000: attempts.clear()
    @app.post('/api/auth/<action>')
    def auth(action):
        if action=='logout': session.clear(); return jsonify(ok=True)
        if action not in ['login','register']: raise ValueError('Unknown account action.')
        if action=='register' and db().execute('SELECT 1 FROM users LIMIT 1').fetchone():
            return jsonify(error='Registration is closed. Sign in with the owner account.',registration_open=False),403
        rate_limit(); data=body()
        email=str(data.get('email','')).strip().lower(); password=str(data.get('password',''))
        if '@' not in email or len(email)>254 or len(password)>256: raise ValueError('Enter a valid email and password.')
        row=db().execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        if action=='register':
            if len(password)<10: raise ValueError('Use a password with at least 10 characters.')
            name=str(data.get('name','')).strip()[:80]
            if not name: raise ValueError('Enter your name.')
            if row: raise ValueError('An account with this email already exists.')
            try: uid=write('INSERT INTO users(email,name,password,preferences,created_at) VALUES(?,?,?,?,?)',(email,name,generate_password_hash(password),json.dumps(DEFAULTS),now()))
            except sqlite3.IntegrityError:
                db().rollback()
                return jsonify(error='Registration is closed. Sign in with the owner account.',registration_open=False),403
        else:
            if not row or row['id']!=db().execute('SELECT MIN(id) FROM users').fetchone()[0] or not check_password_hash(row['password'],password): raise ValueError('Email or password is incorrect.')
            uid=row['id']
        session.clear(); session.update(user_id=uid,csrf=secrets.token_hex(24)); session.permanent=True
        return jsonify(user=profile(user()),csrf=session['csrf'])
    def finite(value,low,high,label):
        if isinstance(value,bool): raise ValueError(f'{label} must be a number.')
        try: number=float(value)
        except (ValueError,TypeError): raise ValueError(f'{label} must be a number.')
        if not math.isfinite(number) or not low<=number<=high: raise ValueError(f'{label} must be between {low} and {high}.')
        return number
    @app.patch('/api/profile')
    @authenticated
    def update_profile():
        data=body(); preferences=json.loads(user()['preferences']); incoming=data.get('preferences',{})
        if not isinstance(incoming,dict): raise ValueError('Invalid preferences.')
        for key,value in incoming.items():
            if key not in DEFAULTS: raise ValueError(f'Unknown setting: {key}')
            if key=='timezone':
                try: ZoneInfo(value)
                except (ZoneInfoNotFoundError,TypeError): raise ValueError('Enter a valid IANA timezone, such as Pacific/Auckland.')
            if key in ['latitude','longitude'] and value is not None: value=finite(value,-90 if key=='latitude' else -180,90 if key=='latitude' else 180,key)
            if key in ['weather_enabled','calendar_enabled','application'] and not isinstance(value,bool): raise ValueError('Invalid toggle setting.')
            if key=='projection': value=finite(value,0,100,key)
            if key=='variety': value=finite(value,0,2,key)
            if key=='favorite_bias': value=finite(value,0,10,key)
            if key=='location': value=str(value)[:100]
            if key=='occasion' and value not in ['automatic']+OCCASIONS: raise ValueError('Unknown occasion.')
            if key=='units' and value not in ['celsius','fahrenheit']: raise ValueError('Invalid units.')
            if key=='weights':
                if not isinstance(value,dict) or set(value)!=set(WEIGHTS): raise ValueError('Supply all scoring weights.')
                value={k:finite(v,0,100,k) for k,v in value.items()}
                if sum(value.values())<=0: raise ValueError('At least one weight must be positive.')
                if value['rotation']/sum(value.values())>.04: raise ValueError('Rotation must stay at or below 4% of the total.')
            preferences[key]=value
        if (preferences['latitude'] is None)!=(preferences['longitude'] is None): raise ValueError('Supply both coordinates or clear both.')
        write('UPDATE users SET preferences=? WHERE id=?',(json.dumps(preferences),session['user_id']))
        return jsonify(user=profile(user()))
    def fragrance_data(data):
        result={}
        for key in ['brand','name','concentration','family','notes','top_notes','middle_notes','base_notes','accords','tags']:
            result[key]=str(data.get(key,'')).strip()[:2000]
        if not result['brand'] or not result['name']: raise ValueError('Brand and fragrance name are required.')
        attributes=data.get('attributes',{})
        if not isinstance(attributes,dict): raise ValueError('Invalid fragrance attributes.')
        result['attributes']={k:finite(v,0,100,k) for k,v in attributes.items() if k in ATTRIBUTES and v is not None and v!=''}
        for key,low,high in [('longevity',.5,48),('rating',1,5),('bottle_size',1,2000),('personal_longevity',.5,48)]:
            result[key]=finite(data[key],low,high,key) if data.get(key) is not None and data.get(key)!='' else None
        for key,options in [('occasions',OCCASIONS),('dayparts',['morning','afternoon','evening','night']),('seasons',['spring','summer','autumn','winter'])]:
            value=data.get(key,[])
            if not isinstance(value,list) or any(v not in options for v in value): raise ValueError(f'Invalid {key}.')
            result[key]=value
        result['favorite']=bool(data.get('favorite',False))
        result['source']='fictional example' if data.get('source')=='fictional example' else 'user-entered estimates'
        return result
    def metadata_for(external_id,refresh=False):
        external_id=str(external_id)
        if len(external_id)>300:raise ValueError('Invalid fragrance identifier.')
        cached=db().execute('SELECT * FROM catalog_metadata WHERE provider=? AND external_id=?',(catalog_provider.name,external_id)).fetchone()
        # Local files already support hot refresh. Remote metadata expires after seven days.
        local=catalog_provider.name!='fragella'
        if cached and not refresh and not local:
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(cached['retrieved_at'])).total_seconds()
            if age<metadata_ttl:return json.loads(cached['data'])
        preview=None
        if catalog_provider.name=='fragella'and not refresh:
            # Fragella search returns a complete profile. Reuse only the selected
            # profile; don't persist the entire external search result catalog.
            with catalog_lock:
                for timestamp,records in search_cache.values():
                    if time.time()-timestamp<900:
                        preview=next((m for m in records if m['external_id']==external_id),None)
                        if preview:break
        metadata=preview or catalog_provider.get_fragrance(external_id)
        if metadata['provider']!=catalog_provider.name or str(metadata['external_id'])!=external_id:raise CatalogError('The provider returned a different fragrance. Please search again.')
        write('INSERT INTO catalog_metadata(provider,external_id,retrieved_at,data) VALUES(?,?,?,?) ON CONFLICT(provider,external_id) DO UPDATE SET retrieved_at=excluded.retrieved_at,data=excluded.data',
            (metadata['provider'],metadata['external_id'],metadata['retrieved_at'],json.dumps(metadata)))
        # Retain owned metadata, but expire unowned detail previews after one day.
        write("DELETE FROM catalog_metadata WHERE retrieved_at<? AND NOT EXISTS(SELECT 1 FROM fragrances f WHERE json_extract(f.data,'$.metadata.provider')=catalog_metadata.provider AND json_extract(f.data,'$.metadata.external_id')=catalog_metadata.external_id)",((datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),))
        return metadata
    def current_metadata(external_id):
        # A just-selected snapshot makes Add a local database operation.
        cached=db().execute('SELECT data FROM catalog_metadata WHERE provider=? AND external_id=?',(catalog_provider.name,str(external_id))).fetchone()
        if cached:
            m=json.loads(cached['data'])
            if (datetime.now(timezone.utc)-datetime.fromisoformat(m['retrieved_at'])).total_seconds()<metadata_ttl:return m
        return metadata_for(external_id)
    def already_owned(metadata):
        row=db().execute("SELECT id FROM fragrances WHERE user_id=? AND archived=0 AND ((json_extract(data,'$.metadata.provider')=? AND json_extract(data,'$.metadata.external_id')=?) OR json_extract(data,'$.metadata.identity')=?)",(session['user_id'],metadata['provider'],metadata['external_id'],metadata.get('identity'))).fetchone()
        return row['id']if row else None
    @app.get('/api/catalog/status')
    @authenticated
    def catalog_status():return jsonify(catalog=catalog_provider.status())
    @app.get('/api/catalog/search')
    @authenticated
    def catalog_search():
        query=request.args.get('q','').strip()
        brand=request.args.get('brand','').strip()
        gender=request.args.get('gender','').strip()
        page=request.args.get('page','1')
        if page not in ['1','2']:raise ValueError('Invalid search page.')
        page=int(page)
        if len(brand)>80:raise ValueError('Use a shorter brand name.')
        if gender not in ['', 'men', 'women', 'unisex', 'men,unisex', 'women,unisex']:raise ValueError('Invalid fragrance audience filter.')
        if len(query)>150:raise ValueError('Use a shorter search query.')
        if len(query)<3:return jsonify(results=[],catalog=catalog_provider.status())
        cache_key=(query.casefold(),brand.casefold(),gender,page)
        with catalog_lock:cached=search_cache.get(cache_key)
        if cached and time.time()-cached[0]<900:results=cached[1]
        else:
            results,more=catalog_provider.search_page(query,page,brand,gender)
            with catalog_lock:
                if len(search_cache)>=100:
                    oldest=next(iter(search_cache));search_cache.pop(oldest);search_more.pop(oldest,None)
                search_cache[cache_key]=(time.time(),results)
                search_more[cache_key]=more
        with catalog_lock:has_more=search_more.get(cache_key,False)
        return jsonify(results=[dict(m,owned_id=already_owned(m))for m in results],catalog=catalog_provider.status(),page=page,has_more=has_more)
    @app.get('/api/catalog/fragrances/<path:external_id>')
    @authenticated
    def catalog_detail(external_id):
        m=metadata_for(external_id)
        return jsonify(fragrance=dict(m,owned_id=already_owned(m)))
    @app.post('/api/collection/from-catalog')
    @authenticated
    def add_from_catalog():
        incoming=body()
        if incoming.get('provider')!=catalog_provider.name:raise ValueError('The catalog changed. Search again to select the correct version.')
        if not incoming.get('external_id'):raise ValueError('Choose a fragrance from search results.')
        metadata=current_metadata(incoming['external_id']);duplicate=already_owned(metadata)
        if duplicate:return jsonify(error='This fragrance is already in your collection.',existing_id=duplicate),409
        data=collection_data(metadata)
        fid=write('INSERT INTO fragrances(user_id,data) VALUES(?,?)',(session['user_id'],json.dumps(data)))
        return jsonify(fragrance=dict(data,id=fid)),201
    def collection():
        return [dict(json.loads(r['data']),id=r['id']) for r in db().execute('SELECT * FROM fragrances WHERE user_id=? AND archived=0',(session['user_id'],))]
    @app.get('/api/collection')
    @authenticated
    def get_collection(): return jsonify(collection=collection())
    @app.post('/api/collection')
    @authenticated
    def add_fragrance():
        data=fragrance_data(body()); fid=write('INSERT INTO fragrances(user_id,data) VALUES(?,?)',(session['user_id'],json.dumps(data)))
        return jsonify(fragrance=dict(data,id=fid)),201
    @app.patch('/api/collection/<int:fid>')
    @authenticated
    def edit_fragrance(fid):
        row=owned('fragrances',fid); incoming=body(); original=json.loads(row['data'])
        attribute_changes=incoming.get('attributes',{})
        if not isinstance(attribute_changes,dict):raise ValueError('Invalid fragrance attributes.')
        override_keys=set(original.get('overrides',[]))
        if 'attributes' in incoming: incoming['attributes']={**original.get('attributes',{}),**attribute_changes}
        data=fragrance_data({**original,**incoming})
        for attribute in attribute_changes:
            if data['attributes'].get(attribute)!=original.get('attributes',{}).get(attribute):override_keys.add('attributes.'+attribute)
        for key in incoming:
            if key in data and key not in ['attributes','source']and data[key]!=original.get(key):override_keys.add(key)
        if original.get('metadata'):
            data.update(metadata=original['metadata'],source=original['source'],overrides=sorted(override_keys),provenance=original.get('provenance',{}).copy())
            for key in override_keys:data['provenance'][key]=dict(source='user')
        write('UPDATE fragrances SET data=?,archived=? WHERE id=?',(json.dumps(data),int(bool(incoming.get('archived',row['archived']))),fid))
        return jsonify(fragrance=dict(data,id=fid))
    @app.post('/api/collection/<int:fid>/refresh-metadata')
    @authenticated
    def refresh_fragrance_metadata(fid):
        row=owned('fragrances',fid);original=json.loads(row['data']);metadata=original.get('metadata')
        if not metadata:raise ValueError('This fragrance was added manually and has no provider record.')
        if metadata['provider']!=catalog_provider.name:raise ValueError('Restore this fragrance’s provider configuration before refreshing its metadata.')
        metadata=metadata_for(metadata['external_id'],refresh=True)
        data=merge_metadata(original,metadata)
        write('UPDATE fragrances SET data=? WHERE id=?',(json.dumps(data),fid))
        return jsonify(fragrance=dict(data,id=fid))
    @app.delete('/api/collection/<int:fid>')
    @authenticated
    def archive(fid):
        owned('fragrances',fid); write('UPDATE fragrances SET archived=1 WHERE id=?',(fid,)); return jsonify(ok=True)
    @app.get('/api/events')
    @authenticated
    def get_events():
        enabled=json.loads(user()['preferences'])['calendar_enabled']
        return jsonify(events=events() if enabled else [])
    def events(): return [dict(json.loads(r['data']),id=r['id']) for r in db().execute('SELECT * FROM events WHERE user_id=?',(session['user_id'],))]
    @app.post('/api/events/import')
    @authenticated
    def upload_events():
        prefs=json.loads(user()['preferences'])
        if not prefs['calendar_enabled']: raise ValueError('Enable calendar context before importing.')
        result=import_calendar(str(body().get('ics','')),prefs['timezone'])
        # Replace atomically after the entire file has passed validation.
        with db():
            db().execute('DELETE FROM events WHERE user_id=?',(session['user_id'],))
            db().executemany('INSERT INTO events(user_id,data) VALUES(?,?)',[(session['user_id'],json.dumps(e)) for e in result])
        return jsonify(count=len(result))
    @app.delete('/api/events')
    @authenticated
    def clear_events(): write('DELETE FROM events WHERE user_id=?',(session['user_id'],)); return jsonify(ok=True)
    def wears(): return [dict(id=r['id'],fragrance_id=r['fragrance_id'],recommendation_id=r['recommendation_id'],created_at=r['created_at'],snapshot=json.loads(r['snapshot']),feedback=json.loads(r['feedback']) if r['feedback'] else None) for r in db().execute('SELECT * FROM wears WHERE user_id=? ORDER BY id DESC',(session['user_id'],))]
    @app.post('/api/recommendations')
    @authenticated
    def recommend():
        data=body(); prefs=json.loads(user()['preferences']); mode=data.get('mode','now')
        if mode not in ['now','tonight','event']: raise ValueError('Unknown recommendation mode.')
        weather,warning=weather_for(prefs)
        context=build_context(prefs,weather,events() if prefs['calendar_enabled'] else [],mode=mode,event_id=data.get('event_id'))
        candidates=rank(collection(),context,prefs,wears())
        snapshot=dict(context=context,candidates=candidates,warning=warning,mode=mode,application=prefs['application'],weights=prefs['weights'],engine_version=3)
        rid=write('INSERT INTO recommendations(user_id,created_at,snapshot) VALUES(?,?,?)',(session['user_id'],now(),json.dumps(snapshot)))
        return jsonify(dict(snapshot,id=rid))
    @app.get('/api/history')
    @authenticated
    def history():
        recs=[dict(id=r['id'],created_at=r['created_at'],snapshot=json.loads(r['snapshot'])) for r in db().execute('SELECT * FROM recommendations WHERE user_id=? ORDER BY id DESC LIMIT 100',(session['user_id'],))]
        return jsonify(wears=wears(),recommendations=recs)
    @app.post('/api/wears')
    @authenticated
    def add_wear():
        data=body(); rec=owned('recommendations',data.get('recommendation_id')); snapshot=json.loads(rec['snapshot'])
        candidate=next((c for c in snapshot['candidates'] if c['fragrance']['id']==data.get('fragrance_id')),None)
        if not candidate: raise ValueError('Select a fragrance from this recommendation.')
        if snapshot['mode']!='now': raise ValueError('Switch to Wear Now to record what you apply now.')
        if (datetime.now(timezone.utc)-datetime.fromisoformat(rec['created_at'])).total_seconds()>3600: raise ValueError('Refresh your recommendation before recording a wear.')
        if db().execute('SELECT id FROM wears WHERE recommendation_id=? AND user_id=?',(rec['id'],session['user_id'])).fetchone(): raise ValueError('This recommendation already has a wear recorded.')
        fid=candidate['fragrance']['id']; owned('fragrances',fid)
        if owned('fragrances',fid)['archived']: raise ValueError('This fragrance has been archived. Refresh your recommendation.')
        actual=finite(data['sprays'],1,20,'sprays') if data.get('sprays') is not None else None
        wear_snapshot=dict(context=snapshot['context'],candidate=candidate,actual_sprays=actual)
        wid=write('INSERT INTO wears(user_id,fragrance_id,recommendation_id,created_at,snapshot) VALUES(?,?,?,?,?)',(session['user_id'],fid,rec['id'],now(),json.dumps(wear_snapshot)))
        return jsonify(id=wid),201
    @app.post('/api/wears/<int:wid>/feedback')
    @authenticated
    def feedback(wid):
        owned('wears',wid); data=body(); rating=finite(data.get('rating'),1,5,'rating')
        strength=data.get('strength','perfect')
        if strength not in ['perfect','too strong','too weak']: raise ValueError('Unknown strength feedback.')
        longevity=finite(data['longevity'],.5,48,'longevity') if data.get('longevity') not in [None,''] else None
        result=dict(rating=rating,strength=strength,longevity=longevity,note=str(data.get('note',''))[:2000])
        write('UPDATE wears SET feedback=? WHERE id=?',(json.dumps(result),wid)); return jsonify(ok=True)
    @app.get('/api/export')
    @authenticated
    def export(): return jsonify(profile=profile(user()),collection=collection(),events=events(),history=history().get_json())
    return app
