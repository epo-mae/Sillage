import unittest,uuid
from pathlib import Path
from unittest.mock import patch
from sillage.app import create_app
from sillage.engine import WEIGHTS,score,rank


class PrioritiesTests(unittest.TestCase):
    def setUp(self):
        self.path=Path(__file__).resolve().parent.parent/'data'/('test-priorities-'+uuid.uuid4().hex+'.db')
        self.app=create_app(self.path,testing=True);self.client=self.app.test_client();self.csrf=self.client.get('/api/session').json['csrf']
        r=self.post('/auth/register',dict(name='Owner',email='owner@example.com',password='owner-password'));self.csrf=r.json['csrf']
        self.ids=[]
        for name,rating,longevity in [('Favorite',5,2),('Long lasting',2,12)]:
            self.ids.append(self.post('/collection',dict(brand='Fixture',name=name,rating=rating,longevity=longevity,attributes={'projection':50})).json['fragrance']['id'])
    def tearDown(self):
        for suffix in ['', '-wal','-shm']:Path(str(self.path)+suffix).unlink(missing_ok=True)
    def post(self,path,data):return self.client.post('/api'+path,json=data,headers={'X-CSRF-Token':self.csrf})
    def priority(self,key):return {k:10 if k==key else 0 for k in WEIGHTS}
    def test_preview_changes_ranking_without_saving_anything(self):
        before=self.client.get('/api/session').json['user']['preferences']
        a=self.post('/recommendations/preview',dict(importance=self.priority('preference')))
        self.assertEqual(a.status_code,200);a=a.json
        b=self.post('/recommendations/preview',dict(importance=self.priority('longevity'),preview_token=a['preview_token'])).json
        self.assertEqual(a['candidates'][0]['fragrance']['id'],self.ids[0])
        self.assertEqual(b['candidates'][0]['fragrance']['id'],self.ids[1])
        self.assertEqual(a['context'],b['context'])
        self.assertEqual(self.client.get('/api/session').json['user']['preferences'],before)
        history=self.client.get('/api/history').json
        self.assertEqual(history['recommendations'],[]);self.assertEqual(history['wears'],[])
        self.assertEqual(self.client.get('/api/layerings').json['wears'],[])
    def test_preview_context_is_signed_and_weather_frozen(self):
        with patch('sillage.app.weather_for',return_value=({'current':{'temperature':9}},None)) as weather:
            a=self.post('/recommendations/preview',dict(importance=self.priority('preference'))).json
            self.post('/recommendations/preview',dict(importance=self.priority('longevity'),preview_token=a['preview_token']))
            self.assertEqual(weather.call_count,1)
        self.assertEqual(a['context']['temperature'],9)
        for token in ['tampered',{'context':{'temperature':30}}]:
            self.assertEqual(self.post('/recommendations/preview',dict(importance=self.priority('preference'),preview_token=token)).status_code,400)
    def test_priorities_validation_and_explicit_save(self):
        for value in [{},dict.fromkeys(WEIGHTS,0),{**self.priority('preference'),'preference':11},{**self.priority('preference'),'preference':True}]:
            self.assertEqual(self.post('/recommendations/preview',dict(importance=value)).status_code,400)
        importance=self.priority('preference')
        r=self.client.patch('/api/profile',json={'preferences':{'importance':importance}},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(r.status_code,200);self.assertEqual(r.json['user']['preferences']['importance'],importance)
        self.assertEqual(r.json['user']['preferences']['weights'],importance)
        self.assertEqual(self.app.test_client().post('/api/recommendations/preview',json={'importance':importance}).status_code,403)
    def test_boundary_validation_and_stale_recommendation_cannot_bypass_it(self):
        with patch('sillage.app.weather_for',return_value=({'current':{'temperature':9}},None)):
            rec=self.post('/recommendations',{}).json
        url='/api/collection/'+str(self.ids[0]);headers={'X-CSRF-Token':self.csrf}
        for limits in [dict(min_temperature=20,max_temperature=10),dict(min_temperature=-100),dict(avoid_confined='false')]:
            self.assertEqual(self.client.patch(url,json={'limits':limits},headers=headers).status_code,400)
        self.assertEqual(self.client.patch(url,json={'limits':{'min_temperature':12}},headers=headers).status_code,200)
        self.assertEqual(self.post('/wears',dict(fragrance_id=self.ids[0],recommendation_id=rec['id'])).status_code,400)
        preview=self.post('/recommendations/preview',dict(importance=self.priority('preference'),recommendation_id=rec['id'])).json
        candidate=next(c for c in preview['candidates'] if c['fragrance']['id']==self.ids[0])
        self.assertTrue(candidate['excluded']);self.assertEqual(candidate['score'],0)
        self.assertEqual(preview['candidates'][-1]['fragrance']['id'],self.ids[0])


class JudgingTests(unittest.TestCase):
    def test_percentages_are_actual_normalized_shares(self):
        f=dict(id=1,attributes={'projection':50},rating=4)
        c=dict(now='2026-11-01T12:00:00+00:00',environment='unknown',occasion='unknown',daypart='afternoon',season=None,duration=4)
        r=score(f,c,{'projection':50},[],{**WEIGHTS,'rotation':100})
        self.assertAlmostEqual(sum(r['shares'].values()),100,delta=.01)
        self.assertLessEqual(r['shares']['rotation'],4)
        self.assertNotIn('environment',r['shares'])
        for k in r['shares']:self.assertAlmostEqual(r['contributions'][k],r['components'][k]*r['shares'][k]/100,delta=.02)
    def test_personal_boundaries_override_priorities_but_not_unknown_context(self):
        f=dict(id=1,attributes={},rating=5,limits={'min_temperature':12,'max_temperature':25,'avoid_confined':True})
        c=dict(now='2026-11-01T12:00:00+00:00',temperature=9,environment='unknown',occasion='unknown',daypart='afternoon',season=None,duration=4)
        r=score(f,c,{},[],{**WEIGHTS,'temperature':0})
        self.assertTrue(r['excluded']);self.assertEqual(r['score'],0)
        self.assertFalse(score(f,{**c,'temperature':None},{},[])['excluded'])
        self.assertTrue(score(f,{**c,'temperature':18,'environment':'confined'},{},[])['excluded'])
        self.assertTrue(score(f,{**c,'temperature':30},{},[])['excluded'])
        self.assertFalse(score(f,{**c,'temperature':12},{},[])['excluded'])
        self.assertFalse(score({**f,'limits':None},c,{},[])['excluded'])
