const test=require('node:test'),assert=require('node:assert/strict');
require('../lcm-cv-query.js');
const q=globalThis.LcmCvQuery,p='projeto-a',b='projeto-b';
const period={since:'2026-01-01',until:'2026-11-13'};
const group=(project,new_date,dates,whatsapp=false)=>({project,new_date,whatsapp_acquisition:whatsapp,entries:dates.map(date=>({date,stage:2}))});
const source={schema_version:2,classification_version:1,validated:true,cohort_mode:'prospect_date',period,prospects:[
 group(p,'2026-01-03',['2026-01-03','2026-09-02'],true),
 group(p,null,['2026-01-08','2026-09-04']),
 group(p,'2026-09-10',['2026-09-10']),
 // O mesmo cliente de janeiro pode retornar em outro empreendimento.
 group(b,null,['2026-09-05'],true),
 group(b,'2026-01-06',['2026-01-06'])
]};
test('novos e retornos adicionais são grupos exclusivos e conciliam com o funil',()=>{
 const result=q.entries(source,[p,b],period.since,period.until);
 assert.deepEqual(result.totals,{new:3,returning:2,prospect:5,whatsapp_new:1,whatsapp_returning:1});
 assert.equal(result.totals.new+result.totals.returning,result.totals.prospect);
 for(const project of [p,b])assert.equal(result.projects[project].prospect,q.funnelRow(source,project,period.since,period.until).counts.prospect);
 assert.equal(result.daily[p]['2026-01-03'].new,1);
 assert.equal(result.daily[p]['2026-01-03'].whatsapp_new,1);
 assert.equal(Object.values(result.daily[p]).reduce((sum,day)=>sum+day.new,0),result.projects[p].new);
});
test('novo em janeiro vira retorno adicional no recorte de setembro',()=>{
 const result=q.entries(source,[p,b],'2026-09-01','2026-09-30');
 assert.deepEqual(result.totals,{new:1,returning:3,prospect:4,whatsapp_new:0,whatsapp_returning:2});
 assert.equal(result.daily[p]['2026-09-02'],undefined);
 assert.equal(result.daily[p]['2026-09-10'].new,1);
});
test('cadastro e vários retornos no mesmo recorte contam uma vez como novo',()=>{
 const only={...source,prospects:[group(p,'2026-09-01',['2026-09-01','2026-09-03','2026-09-10'],true)]};
 assert.deepEqual(q.entries(only,[p],'2026-09-01','2026-09-30').totals,{new:1,returning:0,prospect:1,whatsapp_new:1,whatsapp_returning:0});
});
test('seleção por projeto e total respeitam a mesma contagem por empreendimento',()=>{
 const a=q.entries(source,[p,p],period.since,period.until);
 const other=q.entries(source,[b],period.since,period.until);
 assert.equal(a.totals.prospect,3);assert.equal(other.totals.prospect,2);
 assert.equal(a.totals.prospect+other.totals.prospect,q.entries(source,[p,b],period.since,period.until).totals.prospect);
 assert.equal(other.totals.returning,1);
});
test('zero é exibido somente quando o período está coberto e não há entradas',()=>{
 assert.deepEqual(q.entries(source,[p],'2026-02-01','2026-02-28').totals,{new:0,returning:0,prospect:0,whatsapp_new:0,whatsapp_returning:0});
 assert.equal(q.entries(source,[p],'2025-12-01','2026-01-31'),null);
 assert.equal(q.entries(source,[p],'2026-09-30','2026-09-01'),null);
 assert.equal(q.entries(source,[p],'2026-02-30','2026-03-01'),null);
});
test('fonte antiga ou classificação incompleta não gera números por subtração',()=>{
 for(const invalid of [
  {...source,classification_version:undefined},
  {...source,classification_version:2},
  {...source,prospects:[{project:p,entries:[{date:'2026-01-03',stage:0}]}]},
  {...source,prospects:[{...source.prospects[0],whatsapp_acquisition:undefined}]},
  {...source,prospects:[group(p,'2026-01-05',['2026-01-03'])]},
  {...source,prospects:[group(p,'2026-02-30',['2026-02-30'])]},
  {...source,prospects:[group(p,null,['2026-01-03','2026-01-03'])]}
 ])assert.equal(q.entries(invalid,[p],period.since,period.until),null);
 assert.equal(q.entries(source,[],period.since,period.until),null);
});
