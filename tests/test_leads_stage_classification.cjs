const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const context={};vm.runInNewContext(fs.readFileSync('lcm-leads-stage-config.js','utf8'),context);
const s=context.LcmLeadStages;
test('classificação dos seis grupos LCM',()=>{
 for(const value of ['PROSPECÇÃO','Novo Lead'])assert.equal(s.classify(value),'PROSPECÇÃO');
 for(const value of ['Contato','CAD/C 1','CAD / C 2','CAD/C 3','CAD/C 4','CAD/C 5','CAD/C 6','CAD/C 7'])
   assert.equal(s.classify(value),'ATENDIMENTO');
 for(const value of ['Agendamento','CAD/A 1','CAD/A 3','CAD/A 7','CAD/A 14','CAD/A 20'])
   assert.equal(s.classify(value),'AGENDAMENTO');
 assert.equal(s.classify('VISITA'),'VISITA');
 assert.equal(s.classify('Análise de Crédito'),'ANÁLISE DE CRÉDITO');
 assert.equal(s.classify('Venda Realizada'),'VENDA');
 for(const value of ['CAD/C 8','CAD/A 8','SEM RESPOSTA','PERDIDO',''])
   assert.equal(s.classify(value),null);
});
test('sequência acumulada literal, sem inserir CAD/C 3 ou 6',()=>{
 const expected=['PROSPECÇÃO','CONTATO','CAD/C 1','CAD/C 2','CAD/C 4','CAD/C 5','CAD/C 7',
 'AGENDAMENTO','CAD/A 1','CAD/A 3','CAD/A 7','CAD/A 14','CAD/A 20','VISITA','ANÁLISE DE CRÉDITO','VENDA REALIZADA'];
 assert.deepEqual(Array.from(s.detailed),expected);
 assert.equal(s.detailedStep('Novo Lead'),'PROSPECÇÃO');
 assert.equal(s.detailedStep('CAD/C 3'),null);
});
test('atual uma situação por lead e empreendimento',()=>{
 const result=s.current([
  {project:'A',lead_id:1,situation:'Novo Lead'},
  {project:'A',lead_id:1,situation:'Novo Lead'},
  {project:'A',lead_id:2,situation:'CAD/C 7'},
  {project:'B',lead_id:1,situation:'Visita'},
  {project:'B',lead_id:3,situation:'Desconhecido'},
  {project:'A',lead_id:'',situation:'Contato'}
 ]);
 assert.equal(result.distinct,4);
 assert.equal(result.totals['PROSPECÇÃO'],1);
 assert.equal(result.totals['ATENDIMENTO'],1);
 assert.equal(result.totals['VISITA'],1);
 assert.equal(result.excluded.duplicate,1);
 assert.equal(result.excluded.unknown,1);
 assert.equal(result.excluded.missing,1);
});
test('acumulado exige evento explícito para cada etapa',()=>{
 const result=s.cumulative([
  {project:'A',lead_id:1,situation:'CAD/C 7'},
  {project:'A',lead_id:1,situation:'CAD/C 7'},
  {project:'A',lead_id:2,situation:'CAD/C 4'},
  {project:'A',lead_id:2,situation:'CAD/C 7'}
 ]);
 assert.equal(result['CAD/C 7'],2);
 assert.equal(result['CAD/C 4'],1);
 assert.equal(result['CAD/C 1'],0);
});
