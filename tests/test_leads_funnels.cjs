const {test}=require('node:test'),assert=require('node:assert/strict');global.LcmLeadsModel=require('../lcm-leads-model.js');const F=require('../lcm-leads-funnels.js');
test('situações atuais mantêm status individuais e descartados fora do funil',()=>{const r=F.current([{status:'CAD/C 4',count:8},{status:'Novo Lead',count:2},{status:'DESCARTADO',count:5},{status:'VENDA REALIZADA',count:1},{status:'CAD/A 3',count:6}]);assert.equal(r.discarded,5);assert.deepEqual(r.stages.map(x=>x.label),['NOVO LEAD','CAD/C 4','CAD/A 3','VENDA REALIZADA']);assert.equal(r.stages.reduce((n,x)=>n+x.value,0)+r.discarded,22);});
test('vendas deduplicam lead, retornos e reservas com limites de data e filtros',()=>{const filters={since:'2026-11-01',until:'2026-11-18',project:'Ipê'};const roster=[{history_key:'a',project:'Ipê'},{history_key:'b',project:'Outro'}];const data=[{key:'a',registered:'2026-01-01',entries:['2026-01-01','2026-11-02','2026-11-04'],events:[{date:'2026-11-05',level:3,source:'reservation_rule'},{date:'2026-11-06',level:4,source:'reservation_sale'},{date:'2026-11-06',level:4,source:'reservation_sale'}]},{key:'b',registered:'2026-11-01',entries:['2026-11-01'],events:[]}];const r=F.sales(data,roster,filters);assert.deepEqual(r.stages.map(x=>x.value),[1,1,1,1,1]);assert.equal(r.returns,1);assert.equal(F.sales(data,roster,{...filters,until:'2026-11-04'}).stages[4].value,0);});
test('crédito sem visita entra por regra, mas visita pendente não vira realizada',()=>{
 const date='2026-11-02';
 const cases=[
  [{date,level:1,source:'visit_scheduled'},{date,level:3,source:'credit_stage'}],
  [{date,level:3,source:'credit_stage'}],
  [{date,level:1,source:'visit_scheduled'},{date,level:2,source:'visit'}],
  [{date,level:1,source:'visit_cancelled'},{date,level:3,source:'credit_stage'}]
 ];
 const records=cases.map((events,i)=>({key:String(i),registered:date,entries:[date],events}));
 const rows=records.map(r=>({history_key:r.key}));
 const {stages}=F.sales(records,rows,{since:date,until:date});
 assert.deepEqual(stages.map(x=>x.value),[4,3,2,3,0]);
 assert.equal(stages[2].inferred,1);
});
