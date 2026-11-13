/* Classificação de etapas comerciais informada pela LCM — 13/11/2026.
   O mapeamento não cria passagens históricas nem comprova atendimento. */
(function(root){
'use strict';
const detailed=[
 'PROSPECÇÃO','CONTATO','CAD/C 1','CAD/C 2','CAD/C 4','CAD/C 5','CAD/C 7',
 'AGENDAMENTO','CAD/A 1','CAD/A 3','CAD/A 7','CAD/A 14','CAD/A 20',
 'VISITA','ANÁLISE DE CRÉDITO','VENDA REALIZADA'
];
const groups=['PROSPECÇÃO','ATENDIMENTO','AGENDAMENTO','VISITA','ANÁLISE DE CRÉDITO','VENDA'];
const norm=value=>String(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'')
 .toUpperCase().replace(/\s+/g,' ').trim();
function classify(raw){
 const s=norm(raw).replace(/\s*\/\s*/g,'/');
 if(['PROSPECCAO','NOVO LEAD'].includes(s))return 'PROSPECÇÃO';
 if(s==='CONTATO'||/^CAD\/C\s*[1-7]$/.test(s))return 'ATENDIMENTO';
 if(s==='AGENDAMENTO'||/^CAD\/A\s*(?:1|3|7|14|20)$/.test(s))return 'AGENDAMENTO';
 if(s==='VISITA')return 'VISITA';
 if(['ANALISE DE CREDITO','ANALISE CREDITO'].includes(s))return 'ANÁLISE DE CRÉDITO';
 if(['VENDA','VENDA REALIZADA'].includes(s))return 'VENDA';
 return null;
}
function detailedStep(raw){
 const s=norm(raw).replace(/\s*\/\s*/g,'/');
 if(s==='NOVO LEAD')return 'PROSPECÇÃO';
 return detailed.find(name=>norm(name).replace(/\s*\/\s*/g,'/')===s)||null;
}
function current(records){
 if(!Array.isArray(records))throw new TypeError('records devem ser uma lista');
 const seen=new Set(),totals=Object.fromEntries(groups.map(g=>[g,0])),excluded={missing:0,unknown:0,duplicate:0};
 for(const record of records){
  const project=String(record.project||'').trim();
  const id=String(record.lead_id||'').trim();
  if(!id||!project){excluded.missing++;continue;}
  const key=JSON.stringify([project,id]);
  if(seen.has(key)){excluded.duplicate++;continue;}
  seen.add(key);
  const g=classify(record.situation);
  if(!g){excluded.unknown++;continue;}
  totals[g]++;
 }
 return {totals,excluded,distinct:seen.size};
}
function cumulative(records){
 if(!Array.isArray(records))throw new TypeError('records devem ser uma lista');
 const sets=Object.fromEntries(detailed.map(name=>[name,new Set()]));
 for(const record of records){
  const project=String(record.project||'').trim(),id=String(record.lead_id||'').trim();
  const name=detailedStep(record.situation);
  if(!project||!id||!name)continue;
  sets[name].add(JSON.stringify([project,id]));
 }
 return Object.fromEntries(detailed.map(name=>[name,sets[name].size]));
}
// Os níveis detalhados não são linearmente obrigatórios: um lead que passou por
// CAD/C 7 não pode ser imputado a CAD/C 4 sem eventos históricos comprovados.
root.LcmLeadStages=Object.freeze({detailed,groups,classify,detailedStep,current,cumulative});
})(typeof globalThis!=='undefined'?globalThis:window);
