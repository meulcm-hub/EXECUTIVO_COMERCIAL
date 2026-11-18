/* Funis independentes: distribuição atual e jornada acumulada por lead. */
(function(root){'use strict';
const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').trim().toUpperCase();
const order=['NOVO LEAD','PROSPECÇÃO','CONTATO','CAD/C 1','CAD/C 2','CAD/C 4','CAD/C 5','CAD/C 7','AGENDAMENTO','CAD/A 1','CAD/A 3','CAD/A 7','CAD/A 14','CAD/A 20','VISITA','ANÁLISE DE CRÉDITO','VENDA REALIZADA'];
function current(rows){const counts=new Map();for(const r of rows){const key=norm(r.status);counts.set(key,(counts.get(key)||0)+(r.count??1));}const discarded=counts.get('DESCARTADO')||0;counts.delete('DESCARTADO');const labels=new Map(order.map(x=>[norm(x),x]));const keys=[...counts.keys()].filter(k=>counts.get(k)>0);keys.sort((a,b)=>{const i=order.findIndex(x=>norm(x)===a),j=order.findIndex(x=>norm(x)===b);return (i<0?order.length-1:i)-(j<0?order.length-1:j)||a.localeCompare(b);});return {stages:keys.map(k=>({label:labels.get(k)||k,value:counts.get(k)})),discarded};}
function sales(records,rows,filters){const eligible=new Set(rows.filter(r=>(!filters.project||norm(r.project)===norm(filters.project))&&(!filters.origin||root.LcmLeadsModel.origin(r)===filters.origin)&&(!filters.owner||r.owner===filters.owner)&&(!filters.status||r.status===filters.status)).map(r=>r.history_key));const counts=[0,0,0,0,0],inferred=[0,0,0,0,0];let returns=0;
 for(const r of records){if(!eligible.has(r.key))continue;const dates=r.entries.filter(d=>d>=filters.since&&d<=filters.until);if(!dates.length)continue;const first=dates.sort()[0];counts[0]++;if(r.registered<filters.since)returns++;const direct=new Set(),viaReservation=new Set();
  for(const e of r.events){if(e.date<first||e.date>filters.until)continue;for(let i=1;i<=e.level;i++){(e.source==='reservation_rule'||(e.source==='reservation_sale'&&i<4)?viaReservation:direct).add(i);}}
  for(let i=1;i<5;i++)if(direct.has(i)||viaReservation.has(i)){counts[i]++;if(!direct.has(i)&&viaReservation.has(i))inferred[i]++;}
 }return {stages:['Prospect','Agendamento','Visita','Análise de Crédito','Venda Realizada'].map((label,i)=>({label,value:counts[i],inferred:inferred[i]})),returns};}
const api={current,sales};root.LcmLeadsFunnels=api;if(typeof module!=='undefined')module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:window);
