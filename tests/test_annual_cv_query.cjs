const test=require('node:test'),assert=require('node:assert/strict');
require('../lcm-cv-query.js');
const q=globalThis.LcmCvQuery;
const p='projeto-a',b='projeto-b',period={since:'2026-01-01',until:'2026-11-12'};
const source={schema_version:2,validated:true,cohort_mode:'prospect_date',as_of:period.until,period,
 prospects:[{project:p,entries:[{date:'2026-01-03',stage:4},{date:'2026-09-02',stage:2},{date:'2026-09-15',stage:0}]},
 {project:p,entries:[{date:'2026-09-04',stage:3}]},{project:b,entries:[{date:'2026-01-03',stage:1}]}]};
test('ano conta cada grupo uma vez; setembro inclui retorno sem duplicá-lo',()=>{
 assert.deepEqual(q.funnelRow(source,p,period.since,period.until).counts,{prospect:2,agendamento:2,visita:2,analise_credito:2,venda_realizada:1});
 assert.deepEqual(q.funnelRow(source,p,'2026-09-01','2026-09-30').counts,{prospect:2,agendamento:2,visita:2,analise_credito:1,venda_realizada:0});
 assert.equal(q.funnelRow(source,p,'2026-09-10','2026-09-30').counts.prospect,1);
 assert.equal(q.funnelRow(source,p,'2026-09-10','2026-09-30').counts.visita,0);
});
test('intervalo fora do histórico ou etapa inválida é recusado',()=>{
 assert.equal(q.funnelRow(source,p,'2025-01-01',period.until),null);
 assert.equal(q.validFunnel({...source,prospects:[{project:p,entries:[{date:'2026-01-01',stage:6}]}]}),false);
});
test('auditoria escolhe entrada da seleção e não junta homônimos',()=>{
 const row={cliente:'Nome fictício',data_entrada:'2026-01-03',entry_dates:['2026-01-03','2026-09-02']};
 assert.equal(q.auditDate(row,'2026-09-01','2026-09-30'),'2026-09-02');
 assert.equal(q.auditDate(row,'2026-02-01','2026-02-28'),null);
 assert.equal([row,{...row}].filter(r=>q.auditDate(r,period.since,period.until)).length,2);
 assert.equal(q.auditDate({data_entrada:'2026-09-02'},period.since,period.until),'2026-09-02');
});
test('conversões deduplicam entre dias e projetos; indeterminado não vira retorno',()=>{
 const r={schema_version:4,validated:true,period,projects:[p,b],unique_groups:[
 {events:[{project:p,date:'2026-01-01',returning:false},{project:p,date:'2026-09-01',returning:true,whatsapp:true},{project:b,date:'2026-09-02',returning:true,whatsapp:true}]},
 {events:[{project:p,date:'2026-09-03',unclassified:true}]}]};
 const year=q.conversions(r,period.since,period.until);
 assert.equal(year.unique.all,2);assert.equal(year.returning.all,1);
 assert.equal(year.returning[p],1);assert.equal(year.returning[b],1);
 assert.equal(year.returning_whatsapp.all,1);assert.equal(year.unclassified_return.all,1);
 assert.equal(q.conversions(r,'2026-01-01','2026-01-31').returning.all,0);
});
test('formato anterior continua disponível durante a publicação anual',()=>{
 const old={...source,schema_version:1,cohorts:[{project:p,since:period.since,until:period.until,validated:true,counts:{prospect:9}}]};
 assert.equal(q.funnelRow(old,p,period.since,period.until).counts.prospect,9);
 const range={unique:{all:7}};assert.equal(q.conversions({schema_version:3,validated:true,period,range_unique:{[period.since+'|'+period.until]:range}},period.since,period.until),range);
});

