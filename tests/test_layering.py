import json
import sqlite3
import unittest
import uuid
from contextlib import closing
from datetime import datetime,timedelta,timezone
from pathlib import Path

from sillage import layering
from sillage.app import create_app


CONTEXT=dict(now='2026-11-01T20:00:00+00:00',daypart='evening',occasion='unknown',environment='indoor',temperature=18,feels_like=17,humidity=60,wind=8,precipitation=0,duration=4)

def candidate(identifier):
    return dict(fragrance=dict(id=identifier,name='Fragrance '+str(identifier)),score=90,penalties=[],components=dict(temperature=90,time=85,projection=90))

def recipe():
    return dict(id=1,first_id=1,second_id=2,first_sprays=1,second_sprays=1,first={'name':'First'},second={'name':'Second'},available=True)

def evidence(count=3):
    result=[]
    for i in range(count):
        time=(datetime.fromisoformat(CONTEXT['now'])-timedelta(days=i+1)).isoformat()
        result.append(dict(id=i+1,layering_id=1,created_at=time,snapshot=dict(context={**CONTEXT,'now':time},recipe=recipe()),feedback=dict(rating=5,comparison='better together',strength='perfect',longevity=6)))
    return result


class LayeringRulesTests(unittest.TestCase):
    def suggest(self,**kwargs):
        args=dict(recipes=[recipe()],pair_wears=evidence(),single_wears=[],candidates=[candidate(1),candidate(2)],context=CONTEXT)
        args.update(kwargs);return layering.recommendation(**args)
    def test_untried_and_one_day_trials_are_not_recommendations(self):
        self.assertIsNone(self.suggest(pair_wears=[]))
        self.assertIsNone(self.suggest(pair_wears=evidence(2)))
        same=evidence()
        for w in same:w['snapshot']['context']['now']=CONTEXT['now']
        self.assertIsNone(self.suggest(pair_wears=same))
    def test_supported_pair_is_optional_and_has_no_invented_blend_score(self):
        option=self.suggest()
        self.assertEqual(option['positive_days'],3)
        self.assertNotIn('score',option)
        self.assertIn('either fragrance alone',option['reason'])
    def test_weather_and_time_changes_require_matching_evidence(self):
        for changes in [dict(temperature=9),dict(feels_like=8),dict(humidity=90),dict(wind=25),dict(precipitation=2),dict(daypart='morning'),dict(environment='confined'),dict(occasion='work')]:
            with self.subTest(changes=changes):self.assertIsNone(self.suggest(context={**CONTEXT,**changes}))
    def test_unknown_current_factors_are_ignored_not_invented(self):
        c={**CONTEXT,'temperature':None,'humidity':None,'environment':'unknown'}
        self.assertIsNotNone(self.suggest(context=c))
        historical=evidence()
        for w in historical:w['snapshot']['context']['temperature']=None
        self.assertIsNone(self.suggest(pair_wears=historical))
    def test_both_fragrances_must_fit_individually(self):
        for changes in [dict(score=60),dict(score=None),dict(penalties=[dict(amount=30)]),dict(components={'temperature':40}),dict(components={'time':40}),dict(components={'projection':40})]:
            bad={**candidate(2),**changes}
            self.assertIsNone(self.suggest(candidates=[candidate(1),bad]))
        r=recipe();r['available']=False
        self.assertIsNone(self.suggest(recipes=[r]))
    def test_latest_negative_and_insufficient_duration_pause_suggestions(self):
        for key,value in [('comparison','prefer alone'),('strength','too strong'),('rating',2),('longevity',2)]:
            h=evidence();h[0]['feedback'][key]=value
            self.assertIsNone(self.suggest(pair_wears=h))
    def test_consistency_threshold_and_recipe_specific_learning(self):
        history=evidence(4);history[-1]['feedback']['rating']=2
        self.assertIsNone(self.suggest(pair_wears=history))
        history=evidence(5);history[-1]['feedback']['rating']=2
        self.assertIsNotNone(self.suggest(pair_wears=history))
        changed=recipe();changed.update(id=2,first_sprays=2)
        self.assertIsNone(self.suggest(recipes=[changed]))
    def test_pair_must_outperform_best_single_not_just_its_ingredients(self):
        candidates=[candidate(3),candidate(1),candidate(2)]
        self.assertIsNone(self.suggest(candidates=candidates))
        singles=[dict(fragrance_id=3,snapshot={'context':CONTEXT},feedback={'rating':4}) for _ in range(3)]
        self.assertIsNotNone(self.suggest(candidates=candidates,single_wears=singles))
        for w in singles:w['feedback']['rating']=5
        self.assertIsNone(self.suggest(candidates=candidates,single_wears=singles))
    def test_ideas_need_shared_data_and_are_not_suggestions(self):
        a=candidate(1);b=candidate(2)
        self.assertEqual(layering.experiments([a,b],[]),[])
        a['fragrance'].update(attributes={'freshness':80},metadata={'main_accords':[{'name':'woody'},{'name':'citrus'}]})
        b['fragrance'].update(attributes={'freshness':30},metadata={'main_accords':[{'name':'woody'},{'name':'amber'}]})
        ideas=layering.experiments([a,b],[])
        self.assertEqual(len(ideas),1);self.assertIn('not evidence',ideas[0]['reason'])


class LayeringApiTests(unittest.TestCase):
    def setUp(self):
        self.path=Path(__file__).resolve().parent.parent/'data'/('test-layer-'+uuid.uuid4().hex+'.db')
        self.app=create_app(self.path,testing=True);self.client=self.app.test_client();self.csrf=self.client.get('/api/session').json['csrf']
        r=self.post('/auth/register',dict(name='Owner',email='owner@example.com',password='owner-password'));self.csrf=r.json['csrf']
        self.ids=[self.post('/collection',dict(brand='Fixture',name=name,attributes={'projection':50},rating=4,longevity=8)).json['fragrance']['id'] for name in ['First','Second']]
        self.data=dict(first_id=self.ids[0],second_id=self.ids[1],first_sprays=1,second_sprays=1,notes='Test recipe')
        self.rid=self.post('/layerings',self.data).json['id']
    def tearDown(self):
        for suffix in ['', '-wal','-shm']:Path(str(self.path)+suffix).unlink(missing_ok=True)
    def post(self,path,data):return self.client.post('/api'+path,json=data,headers={'X-CSRF-Token':self.csrf})
    def test_validation_authentication_and_distinct_recipes(self):
        self.assertEqual(self.app.test_client().get('/api/layerings').status_code,401)
        self.assertEqual(self.client.post('/api/layerings',json=self.data).status_code,403)
        self.assertEqual(self.post('/layerings',self.data).status_code,409)
        for changes in [dict(second_id=self.ids[0]),dict(first_id=9999),dict(first_sprays=0),dict(first_sprays=1.5)]:
            self.assertEqual(self.post('/layerings',{**self.data,**changes}).status_code,400)
        self.assertEqual(self.post('/layerings',{**self.data,'first_sprays':2}).status_code,201)
        self.assertIsNone(self.post('/recommendations',{}).json['layering_option'])
    def test_cannot_forge_a_recommended_pair_or_log_a_planned_recommendation(self):
        for mode in ['now','tonight']:
            rec=self.post('/recommendations',dict(mode=mode)).json
            self.assertEqual(self.post(f'/layerings/{self.rid}/wears',dict(recommendation_id=rec['id'])).status_code,400)
        self.assertEqual(self.post(f'/layerings/{self.rid}/wears',dict(recommendation_id=99999)).status_code,400)
        self.assertEqual(self.client.get('/api/layerings').json['wears'],[])
    def test_paired_feedback_preserves_snapshot_without_training_single_bottles(self):
        r=self.post(f'/layerings/{self.rid}/wears',dict(request_id='first-try'));self.assertEqual(r.status_code,201);wid=r.json['id']
        self.assertEqual(self.post(f'/layerings/{self.rid}/wears',dict(request_id='first-try')).status_code,409)
        feedback=dict(rating=5,comparison='better together',strength='perfect',longevity=8,note='Liked the combination')
        self.assertEqual(self.post(f'/layering-wears/{wid}/feedback',feedback).status_code,200)
        rec=self.post('/recommendations',{}).json
        self.assertTrue(all('history' not in c['components'] for c in rec['candidates']))
        self.assertIsNone(rec['layering_option'])
        self.client.delete(f'/api/layerings/{self.rid}',headers={'X-CSRF-Token':self.csrf})
        self.client.delete('/api/collection/'+str(self.ids[0]),headers={'X-CSRF-Token':self.csrf})
        exported=self.client.get('/api/export').json['layering']['wears'][0]
        self.assertEqual(exported['snapshot']['recipe']['first']['name'],'First')
        self.assertEqual(exported['feedback'],feedback)
        self.assertEqual(self.post(f'/layerings/{self.rid}/wears',{}).status_code,400)
        restarted=create_app(self.path,testing=True)
        self.assertIsNotNone(restarted)
    def test_pair_suggestion_and_single_wear_share_one_recommendation_slot(self):
        rec=self.post('/recommendations',{}).json
        recipe=self.client.get('/api/layerings').json['recipes'][0]
        with closing(sqlite3.connect(self.path)) as db:
            for i in range(3):
                when=(datetime.fromisoformat(rec['context']['now'])-timedelta(days=i+1)).isoformat()
                snapshot=dict(recipe=recipe,context={**rec['context'],'now':when},recommended=False)
                db.execute('INSERT INTO layering_wears(user_id,layering_id,created_at,snapshot,feedback) VALUES(?,?,?,?,?)',(1,self.rid,when,json.dumps(snapshot),json.dumps(dict(rating=5,comparison='better together',strength='perfect',longevity=8))))
            db.commit()
        rec=self.post('/recommendations',{}).json
        self.assertEqual(rec['layering_option']['recipe']['id'],self.rid)
        r=self.post(f'/layerings/{self.rid}/wears',dict(recommendation_id=rec['id'],request_id='recommended'));self.assertEqual(r.status_code,201)
        self.assertEqual(self.post('/wears',dict(fragrance_id=self.ids[0],recommendation_id=rec['id'])).status_code,400)
        self.assertEqual(self.post(f'/layerings/{self.rid}/wears',dict(recommendation_id=rec['id'])).status_code,400)
        rec=self.post('/recommendations',{}).json
        self.assertEqual(self.post('/wears',dict(fragrance_id=self.ids[0],recommendation_id=rec['id'])).status_code,201)
        self.assertEqual(self.post(f'/layerings/{self.rid}/wears',dict(recommendation_id=rec['id'])).status_code,400)
