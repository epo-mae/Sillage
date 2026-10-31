import unittest, sqlite3, json, uuid
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from sillage.app import create_app

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.path=Path(__file__).resolve().parent.parent/'data'/('test-'+uuid.uuid4().hex+'.db');self.app=create_app(self.path,testing=True);self.client=self.app.test_client();self.csrf=self.client.get('/api/session').json['csrf'];self.register()
    def tearDown(self):
        for suffix in ['', '-wal', '-shm']:Path(str(self.path)+suffix).unlink(missing_ok=True)
    def post(self,path,data):return self.client.post('/api'+path,json=data,headers={'X-CSRF-Token':self.csrf})
    def register(self):
        r=self.post('/auth/register',dict(name='Tester',email='test@example.com',password='test-password-123'));self.assertEqual(r.status_code,200);self.csrf=r.json['csrf']
    def fragrance(self):
        return self.post('/collection',dict(brand='Test',name='Cedar',attributes={'freshness':50,'warmth':50,'projection':40},longevity=7,rating=4,occasions=['casual'])).json['fragrance']
    def test_end_to_end_persistent_and_immutable(self):
        f=self.fragrance();r=self.post('/recommendations',{}).json
        self.assertEqual(r['candidates'][0]['fragrance']['name'],'Cedar')
        w=self.post('/wears',dict(recommendation_id=r['id'],fragrance_id=f['id']));self.assertEqual(w.status_code,201)
        self.assertEqual(self.post('/wears/'+str(w.json['id'])+'/feedback',dict(rating=5,strength='perfect',longevity=8)).status_code,200)
        edited=self.client.patch('/api/collection/'+str(f['id']),json={'name':'Edited'},headers={'X-CSRF-Token':self.csrf});self.assertEqual(edited.status_code,200)
        history=self.client.get('/api/history').json
        self.assertEqual(history['recommendations'][0]['snapshot']['candidates'][0]['fragrance']['name'],'Cedar')
        self.assertEqual(history['wears'][0]['feedback']['longevity'],8)
        restarted=create_app(self.path,testing=True).test_client();csrf=restarted.get('/api/session').json['csrf'];login=restarted.post('/api/auth/login',json=dict(email='test@example.com',password='test-password-123'),headers={'X-CSRF-Token':csrf});self.assertEqual(login.status_code,200)
        self.assertEqual(restarted.get('/api/collection').json['collection'][0]['name'],'Edited')
    def test_csrf_required(self):self.assertEqual(self.client.post('/api/collection',json={}).status_code,403)
    def test_entry_pages_version_assets_and_prevent_stale_html(self):
        import hashlib
        for url in ['/', '/index.html']:
            response=self.client.get(url)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['Cache-Control'],'no-store')
            for asset in ['app.js','catalog.js','atmosphere.js','style.css','catalog.css','atmosphere.css']:
                expected=hashlib.sha256((Path(__file__).resolve().parent.parent/'static'/asset).read_bytes()).hexdigest()[:16]
                self.assertIn('/'+asset+'?v='+expected,response.text)
                with self.client.get('/'+asset+'?v='+expected) as asset_response:
                    self.assertEqual(asset_response.status_code,200)
    def test_only_owner_can_register(self):
        other=self.app.test_client();token=other.get('/api/session').json['csrf']
        self.assertFalse(other.get('/api/session').json['registration_open'])
        r=other.post('/api/auth/register',json=dict(name='Other',email='other@example.com',password='other-password'),headers={'X-CSRF-Token':token})
        self.assertEqual(r.status_code,403)
        self.assertEqual(other.get('/api/collection').status_code,401)
        self.assertFalse(r.json['registration_open'])
        restarted=create_app(self.path,testing=True).test_client()
        self.assertFalse(restarted.get('/api/session').json['registration_open'])
    def test_database_rejects_second_owner(self):
        with closing(sqlite3.connect(self.path)) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO users(email,name,password,preferences,created_at) VALUES('other@example.com','Other','hash','{}','now')")
    def test_owner_can_login_after_logout(self):
        self.post('/auth/logout',{})
        self.csrf=self.client.get('/api/session').json['csrf']
        self.assertEqual(self.post('/auth/login',dict(email='test@example.com',password='test-password-123')).status_code,200)
    def test_unknown_attributes_no_fabrication(self):
        r=self.post('/collection',dict(brand='Test',name='Unknown'));self.assertEqual(r.json['fragrance']['attributes'],{})
        rec=self.post('/recommendations',{}).json;self.assertEqual(rec['candidates'][0]['confidence'],'Low')
    def test_invalid_metadata(self):
        self.assertEqual(self.post('/collection',dict(brand='Test',name='Bad',attributes={'warmth':200})).status_code,400)
        self.assertEqual(self.post('/collection',dict(brand='Test',name='Bad',longevity='NaN')).status_code,400)
    def test_no_duplicate_wear(self):
        f=self.fragrance();r=self.post('/recommendations',{}).json;data=dict(recommendation_id=r['id'],fragrance_id=f['id'])
        self.assertEqual(self.post('/wears',data).status_code,201);self.assertEqual(self.post('/wears',data).status_code,400)
    def test_planning_cannot_record_current_wear(self):
        f=self.fragrance();r=self.post('/recommendations',{'mode':'tonight'}).json
        self.assertEqual(self.post('/wears',dict(recommendation_id=r['id'],fragrance_id=f['id'])).status_code,400)
    def test_archive_preserves_wear(self):
        f=self.fragrance();r=self.post('/recommendations',{}).json;self.post('/wears',dict(recommendation_id=r['id'],fragrance_id=f['id']))
        self.client.delete('/api/collection/'+str(f['id']),headers={'X-CSRF-Token':self.csrf});self.assertEqual(self.client.get('/api/collection').json['collection'],[]);self.assertEqual(len(self.client.get('/api/history').json['wears']),1)
        restored=self.client.patch('/api/collection/'+str(f['id']),json={'archived':False},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(restored.status_code,200)
        self.assertEqual(self.client.get('/api/collection').json['collection'][0]['id'],f['id'])
        self.assertEqual(len(self.client.get('/api/history').json['wears']),1)
    def test_recommendations_include_every_active_fragrance(self):
        ids=[]
        for i in range(7):
            f=self.post('/collection',dict(brand='Test',name='Fragrance '+str(i),attributes={'freshness':i*10,'warmth':100-i*10})).json['fragrance']
            ids.append(f['id'])
        result=self.post('/recommendations',{}).json
        self.assertEqual({c['fragrance']['id'] for c in result['candidates']},set(ids))
        self.assertTrue(all('contributions' in c and 'penalties' in c for c in result['candidates']))
        self.client.delete('/api/collection/'+str(ids[-1]),headers={'X-CSRF-Token':self.csrf})
        result=self.post('/recommendations',{}).json
        self.assertEqual(len(result['candidates']),6)
        self.assertNotIn(ids[-1],[c['fragrance']['id'] for c in result['candidates']])
    def test_weather_failure_graceful(self):
        self.fragrance()
        with patch('sillage.app.weather_for',return_value=(None,'Provider unavailable')):
            r=self.post('/recommendations',{});self.assertEqual(r.status_code,200);self.assertEqual(r.json['warning'],'Provider unavailable')
    def test_password_not_plaintext(self):
        with closing(sqlite3.connect(self.path))as db:stored=db.execute('SELECT password FROM users').fetchone()[0]
        self.assertNotIn('test-password-123',stored);self.assertTrue(stored.startswith('scrypt:'))
    def test_partial_edit_preserves_user_attributes(self):
        f=self.fragrance();r=self.client.patch('/api/collection/'+str(f['id']),json=dict(attributes={'warmth':80}),headers={'X-CSRF-Token':self.csrf});self.assertEqual(r.json['fragrance']['attributes']['freshness'],50)
    def test_calendar_replace_atomic(self):
        text='BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nDTSTART:20261006T190000Z\nDTEND:20261006T210000Z\nSUMMARY:Dinner\nEND:VEVENT\nEND:VCALENDAR'
        self.assertEqual(self.post('/events/import',{'ics':text}).json['count'],1)
        self.assertEqual(self.post('/events/import',{'ics':'not a calendar'}).status_code,400)
        self.assertEqual(len(self.client.get('/api/events').json['events']),1)

if __name__=='__main__':unittest.main()
