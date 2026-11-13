import json,sys,unittest
from collections import Counter,defaultdict
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import buyer_locations as geo

CITY={'city':'Goiânia','uf':'GO','state':'Goiás','lat':-16.68,'lng':-49.25}
def row(identity,city='Goiânia',neighborhood='Centro',project='Empreendimento'):
 return {'Id. Cliente':identity,'Empreendimento':project,'Cidade':city,'Bairro':neighborhood}
class BuyerLocationsTests(unittest.TestCase):
 def test_deduplication_and_conflicting_locations(self):
  rows=[row('private-'+str(i)) for i in range(7)]+[row('private-0'),row('private-0'),row('private-6','Outra Cidade')]
  cities,neighborhoods,coverage,_=geo.aggregate_locations(rows,{'goiania':[CITY]})
  self.assertEqual(cities[('empreendimento','goiania')],6)
  self.assertEqual(neighborhoods[('empreendimento','goiania','centro')],6)
  self.assertEqual(coverage['customers_conflicting_city'],1)
 def test_homonymous_city_is_not_assigned_an_arbitrary_state(self):
  counts,_,coverage,_=geo.aggregate_locations([row('x','Santa Luzia')],{'santa luzia':[CITY,{**CITY,'uf':'MG'}]})
  self.assertFalse(counts);self.assertEqual(coverage['customers_unresolved_city'],1)
 def test_only_aggregates_above_threshold_are_published(self):
  c=Counter({('p','goiania'):5,('small','goiania'):4});n=Counter({('p','goiania','centro'):5})
  cache={'neighborhoods':{geo.cache_key(CITY,'centro'):{'status':'confirmed','precision':'neighborhood','feature_type':'suburb','city':'Goiânia','uf':'GO','neighborhood':'Centro','lat':-16.67,'lng':-49.25}}}
  report=geo.build_report(c,n,Counter(),defaultdict(Counter),{'goiania':[CITY]},cache)
  self.assertEqual(len(report['cities']),1);self.assertEqual(len(report['neighborhoods']),1)
  self.assertEqual(set(report['cities'][0]),{'project','city','uf','lat','lng','count','precision'})
  self.assertNotIn('Id. Cliente',json.dumps(report));self.assertNotIn('nome',json.dumps(report))
 def test_neighborhood_requires_country_city_state_and_neighborhood_match(self):
  good={'lat':'-16.68','lon':'-49.25','name':'Centro','addresstype':'suburb','address':{'country_code':'br','city':'Goiânia','state':'Goiás','suburb':'Centro'}}
  self.assertIsNotNone(geo.verified_neighborhood([good],CITY,'Centro'))
  for address in ({'country_code':'us'},{'country_code':'br','city':'Outra Cidade','state':'Goiás','suburb':'Centro'},{'country_code':'br','city':'Goiânia','state':'Minas Gerais','suburb':'Centro'}):
   self.assertIsNone(geo.verified_neighborhood([{**good,'address':address}],CITY,'Centro'))
  self.assertIsNone(geo.verified_neighborhood([{**good,'name':'Goiânia','addresstype':'city','address':{'country_code':'br','city':'Goiânia','state':'Goiás'}}],CITY,'Centro'))
 def test_point_of_interest_inside_a_neighborhood_is_not_its_location(self):
  poi={'lat':'-16.68','lon':'-49.25','name':'Centro','addresstype':'shop','type':'mall',
       'address':{'country_code':'br','city':'Goiânia','state':'Goiás','suburb':'Centro'}}
  self.assertIsNone(geo.verified_neighborhood([poi],CITY,'Centro'))
  district={**poi,'addresstype':'suburb'}
  self.assertEqual(geo.verified_neighborhood([district],CITY,'Centro')['feature_type'],'suburb')
  cache={'neighborhoods':{geo.cache_key(CITY,'centro'):{'status':'confirmed','precision':'neighborhood','city':'Goiânia','uf':'GO','neighborhood':'Centro','lat':-16.67,'lng':-49.25}}}
  report=geo.build_report(Counter(),Counter({('p','goiania','centro'):5}),Counter(),defaultdict(Counter),{'goiania':[CITY]},cache)
  self.assertEqual(report['neighborhoods'],[])
 def test_default_cache_only_does_not_call_external_geocoder(self):
  with patch.object(geo,'geocode_neighborhood') as request:geo.refresh_cache({'neighborhoods':{}},{'x':(CITY,'Centro')})
  request.assert_not_called()
