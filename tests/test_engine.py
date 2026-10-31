import unittest
from datetime import datetime, timezone, timedelta
from sillage.engine import score, rank, WEIGHTS
from sillage.context import build_context
from sillage.providers import import_calendar

NOW=datetime(2026,10,6,17,30,tzinfo=timezone.utc)
PREFS=dict(timezone='UTC',latitude=-36,location='Test',projection=50,variety=1)

def fragrance(identifier=1,**changes):
    f=dict(id=identifier,brand='Fixture',name=f'Profile {identifier}',attributes=dict(warmth=80,freshness=20,sweetness=80,richness=80,projection=80,formality=80),longevity=8,rating=4,occasions=['dinner','formal'],dayparts=['evening','night'],seasons=['winter','autumn'],favorite=False)
    f.update(changes);return f

def context(**changes):
    c=build_context(PREFS,now=NOW);c.update(temperature=12,humidity=60,occasion='dinner',environment='indoor',weather={'available':True});c.update(changes);return c

class ScoringTests(unittest.TestCase):
    def test_unknown_environment_and_occasion_are_not_scored(self):
        result=score(fragrance(),context(environment='unknown',occasion='unknown'),PREFS,[])
        for key in ['environment','occasion']:
            self.assertNotIn(key,result['components'])
            self.assertNotIn(key,result['weights'])
            self.assertNotIn(key,result['contributions'])
            self.assertIn(key,result['omitted'])
        self.assertNotIn('surroundings',result['explanation'])
        self.assertNotIn('casual',result['explanation'])
        changed=fragrance(occasions=['work','party'])
        self.assertEqual(result['score'],score(changed,context(environment='unknown',occasion='unknown'),PREFS,[])['score'])
        self.assertAlmostEqual(sum(result['contributions'].values()),result['base'],delta=.08)
    def test_no_plans_does_not_assume_casual(self):
        c=build_context(PREFS,now=NOW)
        self.assertEqual(c['occasion'],'unknown');self.assertEqual(c['environment'],'unknown')
        event=dict(id=1,title='Something',start=NOW.isoformat(),end=(NOW+timedelta(hours=2)).isoformat())
        self.assertEqual(build_context(PREFS,events=[event],now=NOW)['occasion'],'unknown')
        c=build_context({**PREFS,'occasion':'casual'},now=NOW)
        result=score(fragrance(),c,PREFS,[])
        self.assertIn('occasion',result['components']);self.assertNotIn('environment',result['components'])
    def test_missing_ratings_and_history_do_not_receive_default_points(self):
        f=fragrance(rating=None)
        result=score(f,context(),PREFS,[])
        self.assertNotIn('preference',result['components']);self.assertNotIn('history',result['components'])
        wear=dict(fragrance_id=1,created_at=NOW.isoformat(),feedback={'rating':5})
        result=score(f,context(),PREFS,[wear])
        self.assertEqual(result['components']['history'],100)
    def test_unknown_context_has_no_mismatch_penalties(self):
        c=context(temperature=None,humidity=None,environment=None,occasion=None,daypart=None,season=None,duration=None)
        result=score(fragrance(attributes={'formality':0},rating=None,longevity=None),c,{},[])
        self.assertIsNone(result['score']);self.assertEqual(result['penalties'],[])
        self.assertIsNone(result['sprays'])
        self.assertEqual(result['confidence'],'Low')
        self.assertTrue(all(value==0 for value in result['contributions'].values()))
    def test_unscorable_profiles_rank_after_profiles_with_evidence(self):
        missing=fragrance(attributes={},rating=None,longevity=None,dayparts=[],seasons=[],occasions=[])
        known=fragrance(2,rating=4)
        results=rank([missing,known],context(),PREFS,[])
        self.assertEqual(results[0]['fragrance']['id'],2)
        self.assertIsNone(results[-1]['score'])
    def test_heat_hard_penalty(self):
        result=score(fragrance(),context(temperature=35),PREFS,[])
        self.assertTrue(any(p['amount']==30 for p in result['penalties']))
    def test_freezing_night_favors_warm(self):
        warm=fragrance();fresh=fragrance(2,attributes=dict(warmth=10,freshness=95,projection=40))
        self.assertGreater(score(warm,context(temperature=-2),PREFS,[])['components']['temperature'],score(fresh,context(temperature=-2),PREFS,[])['components']['temperature'])
    def test_humidity_rewards_freshness(self):
        wet=context(humidity=95,temperature=27)
        warm=score(fragrance(),wet,PREFS,[])
        fresh=score(fragrance(2,attributes=dict(freshness=95,warmth=10,projection=40)),wet,PREFS,[])
        self.assertGreater(fresh['components']['weather'],warm['components']['weather'])
    def test_confined_professional_penalty(self):
        result=score(fragrance(),context(environment='confined',occasion='work'),PREFS,[])
        self.assertTrue(any('confined' in p['reason'] for p in result['penalties']))
        self.assertLessEqual(result['sprays'],2)
    def test_date_night(self):
        result=score(fragrance(occasions=['date']),context(occasion='date'),PREFS,[])
        self.assertEqual(result['components']['occasion'],96)
    def test_formal_casual_penalty(self):
        result=score(fragrance(attributes={'formality':10}),context(occasion='wedding'),PREFS,[])
        self.assertTrue(any('formal' in p['reason'] for p in result['penalties']))
    def test_outdoor_loud_not_hard_penalized(self):
        result=score(fragrance(),context(environment='outdoor'),PREFS,[])
        self.assertFalse(any('confined' in p['reason'] for p in result['penalties']))
    def test_long_event_weak_penalty(self):
        result=score(fragrance(longevity=2),context(duration=10),PREFS,[])
        self.assertTrue(any(p['amount']==20 for p in result['penalties']))
    def test_missing_weather_omitted(self):
        result=score(fragrance(),context(temperature=None,humidity=None,weather=None),PREFS,[])
        self.assertNotIn('temperature',result['components']);self.assertNotIn('weather',result['components'])
    def test_sparse_metadata_low_confidence(self):
        result=score(fragrance(attributes={},longevity=None,occasions=[],dayparts=[],seasons=[]),context(weather=None),PREFS,[])
        self.assertEqual(result['confidence'],'Low');self.assertTrue(0<=result['score']<=100)
    def test_rotation_capped_sparse(self):
        f=fragrance(attributes={},longevity=None,occasions=[],dayparts=[],seasons=[])
        wears=[dict(fragrance_id=1,created_at=NOW.isoformat(),feedback=None)]*10
        a,b=score(f,context(),PREFS,[]),score(f,context(),PREFS,wears)
        self.assertLessEqual(a['score']-b['score'],4)
    def test_favorite_bounded(self):
        a=score(fragrance(favorite=True),context(),PREFS,[])
        b=score(fragrance(),context(),PREFS,[])
        self.assertLessEqual(a['score']-b['score'],2)
    def test_personal_performance_gradual(self):
        wears=[dict(fragrance_id=1,created_at=NOW.isoformat(),feedback=dict(rating=5,longevity=4))]
        result=score(fragrance(longevity=10),context(),PREFS,wears)
        self.assertEqual(result['personal_longevity'],9)
    def test_reproducible_and_components_sum(self):
        f=fragrance();c=context()
        a=rank([f],c,PREFS,[]);b=rank([f],c,PREFS,[])
        self.assertEqual(a,b)
        self.assertAlmostEqual(sum(a[0]['contributions'].values()),a[0]['base'],delta=.08)
    def test_season_hemisphere_and_unknown(self):
        self.assertEqual(build_context(PREFS,now=NOW)['season'],'spring')
        self.assertEqual(build_context({**PREFS,'latitude':36},now=NOW)['season'],'autumn')
        self.assertIsNone(build_context({**PREFS,'latitude':None},now=NOW)['season'])
    def test_horizon_includes_event_end(self):
        event=dict(id=1,title='Dinner',start=(NOW+timedelta(hours=1)).isoformat(),end=(NOW+timedelta(hours=5)).isoformat())
        c=build_context(PREFS,events=[event],now=NOW)
        self.assertEqual(c['duration'],5);self.assertEqual(c['occasion'],'dinner')
    def test_forecast_outweighs_current_season(self):
        weather={'current':{'temperature':18},'hourly':[{'time':(NOW+timedelta(hours=i)).isoformat(),'temperature':10,'humidity':50}for i in range(4)]}
        c=build_context(PREFS,weather,now=NOW)
        self.assertLess(c['temperature'],13);self.assertEqual(c['season'],'spring')
    def test_calendar_import(self):
        events=import_calendar('BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nDTSTART:20261006T190000Z\nDTEND:20261006T210000Z\nSUMMARY:Dinner\nEND:VEVENT\nEND:VCALENDAR','UTC')
        self.assertEqual(len(events),1);self.assertEqual(events[0]['title'],'Dinner')
    def test_windy_wet_outdoors_weak_profile(self):
        f=fragrance(attributes={'freshness':70,'projection':20})
        dry=score(f,context(environment='outdoor',wind=5,precipitation=0),PREFS,[])
        wet=score(f,context(environment='outdoor',wind=45,precipitation=4),PREFS,[])
        self.assertGreater(dry['components']['weather'],wet['components']['weather'])
    def test_midnight_is_night(self):
        self.assertEqual(build_context(PREFS,now=NOW.replace(hour=1))['daypart'],'night')
    def test_recurring_calendar_not_silently_ignored(self):
        with self.assertRaises(ValueError):import_calendar('BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART:20261006T190000Z\nRRULE:FREQ=DAILY\nEND:VEVENT\nEND:VCALENDAR','UTC')

if __name__=='__main__':unittest.main()
