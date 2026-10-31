import json, sqlite3, unittest, uuid
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
from sillage.catalog import (LocalFragranceProvider, FragellaProvider, FragranceDataProvider,
    CatalogError, normalize_fragella, collection_data, merge_metadata, fuzzy_fit)
from sillage.app import create_app
from sillage.engine import score
from sillage.context import build_context

ROOT=Path(__file__).resolve().parent.parent
ROW={'_id':'test-dior-edp-2020','Brand':'Fixture Dior','Name':'Homme EDP','Year':'2020','OilType':'Eau de Parfum','Gender':'men',
     'rating':'4.3','Longevity':'Long Lasting','Sillage':'Strong','Main Accords':['woody','citrus'],
     'Main Accords Percentage':{'woody':'Dominant','citrus':'Moderate'},'Notes':{'Top':[{'name':'Bergamot'}],'Middle':[],'Base':[{'name':'Cedar'}]},
     'Season Ranking':[{'name':'winter','score':3},{'name':'summer','score':1}],
     'Occasion Ranking':[{'name':'professional','score':3},{'name':'night out','score':1}]}

class FixtureProvider(FragranceDataProvider):
    name='fragella'
    def __init__(self):self.calls=0;self.row=ROW.copy();self.failed=False
    def status(self):return dict(name=self.name,ready=True,evaluation=False,label='Fixture catalog',attribution_url='https://example.com')
    def search_fragrances(self,query):
        self.calls+=1
        if self.failed:raise CatalogError('Provider unavailable')
        return [normalize_fragella(self.row)]
    def get_fragrance(self,external_id):
        self.calls+=1
        if self.failed:raise CatalogError('Provider unavailable')
        if external_id!=self.row['_id']:raise CatalogError('Not found',404)
        return normalize_fragella(self.row)

class ProviderTests(unittest.TestCase):
    def test_sample_search_partial_case_typo_and_alias(self):
        p=LocalFragranceProvider(ROOT/'third_party/fragdb_sample',sample=True)
        for query in ['dior','DIOR SAUVAGE','Dior Sauvge','ysl black opium']:
            self.assertGreater(len(p.search_fragrances(query)),0,query)
        self.assertEqual(p.search_fragrances('totally missing fragrance'),[])
    def test_release_versions_distinct(self):
        a=dict(brand='Dior',name='Homme',year=2011,concentration='EDT')
        b=dict(brand='Dior',name='Homme',year=2020,concentration='EDP')
        self.assertGreater(fuzzy_fit('dior homme',a),0);self.assertGreater(fuzzy_fit('dior homme',b),0)
        self.assertGreater(fuzzy_fit('dior homme edp',b),fuzzy_fit('dior homme edp',a))
    def test_vote_distributions_and_counts_preserved(self):
        p=LocalFragranceProvider(ROOT/'third_party/fragdb_sample',sample=True);m=p.get_fragrance('31861')
        self.assertEqual(m['community_rating']['count'],34073)
        self.assertAlmostEqual(m['community']['seasons']['values']['winter'],.6764)
        self.assertEqual(m['community']['seasons']['counts']['winter'],10200)
        self.assertIsNone(m['community']['seasons']['sample_count'])
        self.assertNotIn('occasions',m['community'])
    def test_missing_reference_notes_not_invented(self):
        p=LocalFragranceProvider(ROOT/'third_party/fragdb_sample',sample=True);m=p.get_fragrance('31861')
        self.assertGreater(m['note_pyramid']['unresolved_count'],0)
        self.assertEqual(m['note_pyramid']['top'],[])
        self.assertIsNone(m['concentration'])
    def test_fragella_normalization_unknown_counts_and_relative_ranks(self):
        m=normalize_fragella(ROW)
        self.assertIsNone(m['community_rating']['count'])
        self.assertEqual(m['community']['seasons']['values']['winter'],1)
        self.assertAlmostEqual(m['community']['seasons']['values']['summer'],1/3)
        self.assertEqual(m['provenance']['attributes.projection']['source'],'inferred')
        self.assertEqual(m['note_pyramid']['top'][0]['name'],'Bergamot')
    def test_api_key_required_and_not_exposed(self):
        with self.assertRaises(CatalogError)as caught:FragellaProvider(None).search_fragrances('Sauvage')
        self.assertIn('FRAGELLA_API_KEY',caught.exception.message)
    def test_duplicate_slug_alias_has_same_identity(self):
        a=normalize_fragella({**ROW,'Brand':'Christian Dior','Name':'Dior Sauvage','OilType':'Eau de Toilette','Year':'2015'})
        b=normalize_fragella({**ROW,'_id':'other-slug','Brand':'Christian Dior','Name':'Dior Sauvage Eau De Toilette','OilType':'Eau de Toilette','Year':'2015'})
        self.assertEqual(a['identity'],b['identity'])
        c=normalize_fragella({**ROW,'Brand':'Christian Dior','Name':'Dior Sauvage','OilType':'Eau de Toilette','Year':'2015','Release Version':'2022 reformulation'})
        self.assertNotEqual(a['identity'],c['identity'])
    def test_fragella_authenticated_request_and_normalized_response(self):
        from io import BytesIO
        with patch('sillage.catalog.urlopen',return_value=BytesIO(json.dumps([ROW]).encode()))as request:
            m=FragellaProvider('test-secret').search_fragrances('Dior homme')[0]
        self.assertEqual(m['name'],'Homme EDP');self.assertEqual(request.call_args.args[0].get_header('X-api-key'),'test-secret')
        self.assertNotIn('test-secret',json.dumps(m))
    def test_filtered_pages_keep_distinct_versions(self):
        from urllib.parse import urlparse,parse_qs
        from io import BytesIO
        raw={'data':[ROW,{**ROW,'_id':'another-release','Name':'Homme Parfum','OilType':'Parfum'}],'pagination':{'has_more':True}}
        with patch('sillage.catalog.urlopen',return_value=BytesIO(json.dumps(raw).encode())) as request:
            rows,more=FragellaProvider('test-secret').search_page('Homme',1,'Dior','men,unisex')
        self.assertEqual(len(rows),2);self.assertTrue(more)
        params=parse_qs(urlparse(request.call_args.args[0].full_url).query)
        self.assertEqual(params['brand'],['Dior']);self.assertEqual(params['gender'],['men,unisex']);self.assertEqual(params['page'],['1'])
        with patch('sillage.catalog.urlopen',return_value=BytesIO(json.dumps(raw).encode())):
            rows,more=FragellaProvider('test-secret').search_page('Homme',2)
        self.assertFalse(more)
    def test_refresh_keeps_overrides(self):
        m=normalize_fragella(ROW);old=collection_data(m)
        old.update(longevity=7,notes='my personal note',rating=5,overrides=['longevity','attributes.projection']);old['attributes']['projection']=30
        updated=merge_metadata(old,normalize_fragella({**ROW,'Sillage':'Enormous'}))
        self.assertEqual(updated['attributes']['projection'],30);self.assertEqual(updated['longevity'],7)
        self.assertEqual(updated['rating'],5);self.assertEqual(updated['notes'],'my personal note')
        self.assertEqual(updated['provenance']['attributes.projection']['source'],'user')
    def test_low_votes_less_confident_than_large_votes(self):
        m=normalize_fragella(ROW);f=collection_data(m);f['id']=1
        c=build_context(dict(timezone='UTC',latitude=36),now=datetime(2026,1,6,18,tzinfo=timezone.utc));c.update(weather={'available':True},temperature=8,humidity=60)
        m['community_rating']['count']=5;small=score(f,c,{},[])
        m['community_rating']['count']=10000;large=score(f,c,{},[])
        self.assertGreater(large['certainty'],small['certainty'])
    def test_one_personal_wear_cannot_override_strong_prior(self):
        m=normalize_fragella(ROW);m['performance']['longevity']['sample_count']=10000
        f=collection_data(m);f['id']=1;c=build_context(dict(timezone='UTC',latitude=36))
        w=dict(fragrance_id=1,created_at=c['now'],feedback=dict(rating=1,longevity=1))
        result=score(f,c,{},[w]);self.assertGreater(result['personal_longevity'],9)
        f['personal_longevity']=6;result=score(f,c,{},[]);self.assertEqual(result['personal_longevity'],6)

class CatalogApiTests(unittest.TestCase):
    def setUp(self):
        self.path=ROOT/'data'/('test-'+uuid.uuid4().hex+'.db');self.provider=FixtureProvider();self.app=create_app(self.path,True,self.provider);self.client=self.app.test_client();self.csrf=self.client.get('/api/session').json['csrf'];r=self.post('/auth/register',dict(name='Catalog Tester',email='test@example.com',password='catalog-password'));self.csrf=r.json['csrf']
    def tearDown(self):
        for suffix in ['', '-wal', '-shm']:Path(str(self.path)+suffix).unlink(missing_ok=True)
    def post(self,path,data):return self.client.post('/api'+path,json=data,headers={'X-CSRF-Token':self.csrf})
    def add(self):
        self.client.get('/api/catalog/fragrances/'+ROW['_id']);return self.post('/collection/from-catalog',dict(provider='fragella',external_id=ROW['_id']))
    def test_search_detail_add_duplicate_and_local_recommendation(self):
        r=self.client.get('/api/catalog/search?q=dior');self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.get('/api/catalog/search?q=DIOR').status_code,200);self.assertEqual(self.provider.calls,1)
        added=self.add();self.assertEqual(added.status_code,201);fid=added.json['fragrance']['id'];calls=self.provider.calls
        duplicate=self.add();self.assertEqual(duplicate.status_code,409)
        self.assertEqual(self.provider.calls,calls)
        self.provider.failed=True;r=self.post('/recommendations',{});self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['candidates'][0]['fragrance']['metadata']['external_id'],ROW['_id'])
        self.assertEqual(self.client.get('/api/catalog/search?q=dior').json['results'][0]['owned_id'],fid)
    def test_user_edits_preserved_and_unchanged_strings_not_overrides(self):
        added=self.add().json['fragrance'];fid=added['id']
        r=self.client.patch('/api/collection/'+str(fid),json=dict(attributes={'projection':25},longevity=str(added['longevity']),notes='My notes'),headers={'X-CSRF-Token':self.csrf})
        self.assertNotIn('longevity',r.json['fragrance']['overrides'])
        self.provider.row={**ROW,'Sillage':'Enormous'};r=self.post('/collection/'+str(fid)+'/refresh-metadata',{})
        self.assertEqual(r.json['fragrance']['attributes']['projection'],25);self.assertEqual(r.json['fragrance']['notes'],'My notes')
        self.assertEqual(r.json['fragrance']['metadata']['attributes']['projection'],100)
    def test_different_external_versions_can_be_added(self):
        self.assertEqual(self.add().status_code,201)
        self.provider.row={**ROW,'_id':'different-release','Year':'2011','OilType':'EDT'}
        self.assertEqual(self.post('/collection/from-catalog',dict(provider='fragella',external_id='different-release')).status_code,201)
        self.assertEqual(len(self.client.get('/api/collection').json['collection']),2)
    def test_provider_failure_and_wrong_provider_are_explicit(self):
        self.provider.failed=True;self.assertEqual(self.client.get('/api/catalog/search?q=missing').status_code,503)
        self.assertEqual(self.post('/collection/from-catalog',dict(provider='other',external_id='id')).status_code,400)
    def test_archived_fragrance_can_be_readded(self):
        fid=self.add().json['fragrance']['id'];self.client.delete('/api/collection/'+str(fid),headers={'X-CSRF-Token':self.csrf});self.assertEqual(self.add().status_code,201)
    def test_catalog_requires_authentication(self):
        anonymous=self.app.test_client();self.assertEqual(anonymous.get('/api/catalog/search?q=Dior').status_code,401)
    def test_search_pages_filters_and_selected_preview_cache(self):
        first=normalize_fragella(ROW)
        second=normalize_fragella({**ROW,'_id':'second-page','Name':'Homme Parfum','OilType':'Parfum'})
        with patch.object(self.provider,'search_page',side_effect=[([first],True),([second],False)]) as search:
            a=self.client.get('/api/catalog/search?q=Homme&brand=Dior&gender=men&page=1').json
            b=self.client.get('/api/catalog/search?q=Homme&brand=Dior&gender=men&page=2').json
            self.assertTrue(a['has_more']);self.assertFalse(b['has_more'])
            self.assertEqual(search.call_args_list[1].args,('Homme',2,'Dior','men'))
            self.client.get('/api/catalog/search?q=Homme&brand=Dior&gender=men&page=2')
            self.assertEqual(search.call_count,2)
        # Page-two entries can be selected without another provider request.
        with patch.object(self.provider,'name','fragella'):
            self.assertEqual(self.client.get('/api/catalog/fragrances/second-page').json['fragrance']['name'],'Homme Parfum')
        self.assertEqual(self.client.get('/api/catalog/search?q=Homme&page=3').status_code,400)
        self.assertEqual(self.client.get('/api/catalog/search?q=Homme&gender=bad').status_code,400)
    def test_add_does_not_accept_client_metadata(self):
        r=self.post('/collection/from-catalog',dict(provider='fragella',external_id=ROW['_id'],brand='Fake',attributes={'projection':0}))
        self.assertEqual(r.json['fragrance']['brand'],'Fixture Dior');self.assertEqual(r.json['fragrance']['attributes']['projection'],80)

if __name__=='__main__':unittest.main()
