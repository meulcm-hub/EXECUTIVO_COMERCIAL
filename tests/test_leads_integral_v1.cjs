const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const js=fs.readFileSync('lcm-leads.js','utf8');
const stages=fs.readFileSync('lcm-leads-stage-config.js','utf8');
const context={};vm.runInNewContext(stages,context);
const part=(a,b)=>{const start=js.indexOf(a);const end=js.indexOf(b,start);assert(start>=0&&end>start);return js.slice(start,end);};
const fn=new Function('state','filters','window','NO_PROJECT',
 part('function projectKey(raw){','function projectTitle(key){')+
 part('function filteredFullCells(){','function renderAllHistory(){')+
 ';return filteredFullCells;');
const rows=[
 {date:'2018-11-27',project:'RESIDENCIAL GREEN PLAZA',origin:'FB',visit_media:'NÃO DISPONÍVEL NA API',status:'PROSPECÇÃO',count:3},
 {date:'2019-02-12',project:'RESIDENCIAL FLORRES DO CERRADO IPÊ',origin:'GE',visit_media:'NÃO DISPONÍVEL NA API',status:'ATENDIMENTO',count:4},
 {date:'2026-01-04',project:'RESIDENCIAL GREEN PLAZA',origin:'FB',visit_media:'NÃO DISPONÍVEL NA API',status:'DESCARTADO',count:5}
];
function run(opts={}){
 const f={since:'2018-11-27',until:'2026-11-14',project:'all',stage:'all',origins:new Set(),visitMedia:new Set(),...opts};
 return fn({allHistory:{validated:true,by_registration_project_origin_status:rows}},()=>f,context,'sem empreendimento')();
}
test('base integral aceita período anterior a 2026 e Green Plaza não fica zerado',()=>{
 assert.equal(run().reduce((n,r)=>n+r.count,0),12);
 assert.equal(run({until:'2020-12-31'}).reduce((n,r)=>n+r.count,0),7);
 assert.equal(run({project:'residencial green plaza'}).reduce((n,r)=>n+r.count,0),8);
 assert.equal(run({project:'residencial flores do cerrado ipe'}).reduce((n,r)=>n+r.count,0),4);
});
test('filtros reais de origem e situação com descartados fora das seis etapas',()=>{
 assert.equal(run({origins:new Set(['GE'])}).reduce((n,r)=>n+r.count,0),4);
 assert.equal(run({stage:'FORA DO FUNIL'}).reduce((n,r)=>n+r.count,0),5);
 assert.equal(run({stage:'PROSPECÇÃO'}).reduce((n,r)=>n+r.count,0),3);
});
test('seleção de várias mídias não duplica o mesmo lead',()=>{
 const one={...rows[0],lead_media:'Facebook Ads',lead_medias:['Facebook Ads','WhatsApp Facebook']};
 const list=[one,rows[1]];
 const selected=fn({allHistory:{validated:true,by_registration_project_origin_status:list}},
  ()=>({since:'2018-11-27',until:'2026-11-14',project:'all',stage:'all',
       origins:new Set(),visitMedia:new Set(['Facebook Ads','WhatsApp Facebook'])}),
  context,'sem empreendimento')();
 assert.equal(selected.length,1);
 assert.equal(selected[0].count,3);
});
test('frontend suporta schema v1 histórico e trata mídia ausente como não disponível',()=>{
 assert.match(js,/!\[1,2,3\]\.includes\(data\?\.schema_version\)/);
 assert.match(js,/lead_media:'NÃO DISPONÍVEL NA COLETA ANTERIOR'/);
 assert.match(js,/\$\('since'\)\.value=data\.earliest_cadastro/);
 assert.equal(run({visitMedia:new Set(['NÃO DISPONÍVEL NA API'])}).length,0);
});
