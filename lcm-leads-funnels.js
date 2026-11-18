/* Funis independentes: distribuição atual e jornada acumulada por lead. */
(function(root){'use strict';
const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').trim().toUpperCase();
const order=['NOVO LEAD','PROSPECÇÃO','CONTATO','CAD/C 1','CAD/C 2','CAD/C 4','CAD/C 5','CAD/C 7','AGENDAMENTO','CAD/A 1','CAD/A 3','CAD/A 7','CAD/A 14','CAD/A 20','VISITA','ANÁLISE DE CRÉDITO','VENDA REALIZADA'];
function current(rows){const counts=new Map();for(const r of rows){const key=norm(r.status);counts.set(key,(counts.get(key)||0)+(r.count??1));}const discarded=counts.get('DESCARTADO')||0;counts.delete('DESCARTADO');const labels=new Map(order.map(x=>[norm(x),x]));const keys=[...counts.keys()].filter(k=>counts.get(k)>0);keys.sort((a,b)=>{const i=order.findIndex(x=>norm(x)===a),j=order.findIndex(x=>norm(x)===b);return (i<0?order.length-1:i)-(j<0?order.length-1:j)||a.localeCompare(b);});return {stages:keys.map(k=>({label:labels.get(k)||k,value:counts.get(k)})),discarded};}
function cohort(records, rows, filters) {
 const eligible = new Map(rows.filter(r =>
  (!filters.project || norm(r.project) === norm(filters.project)) &&
  (!filters.origin || root.LcmLeadsModel.origin(r) === filters.origin) &&
  (!filters.owner || r.owner === filters.owner) &&
  (!filters.status || r.status === filters.status)
 ).map(r => [r.history_key, r]));
 return records.flatMap(record => {
  const row = eligible.get(record.key);
  if (!row) return [];
  const first = record.entries.find(date => date >= filters.since && date <= filters.until);
  return first ? [{record, row, first}] : [];
 });
}
function sales(records,rows,filters,legacy=false){const counts=[0,0,0,0,0],inferred=[0,0,0,0,0];let returns=0;
 for(const {record:r,first} of cohort(records,rows,filters)){counts[0]++;if(r.registered<filters.since)returns++;const direct = new Set();
  const inferredStages = new Set();
  const events = r.events.filter(e => e.date >= first && e.date <= filters.until);
  if (legacy) {
   const recorded = new Set();
   const inferredOnly = new Set();
   for (const event of events) {
    for (let level = 1; level <= event.level; level++) {
     const inferredByReservation = event.source === 'reservation_rule' ||
      (event.source === 'reservation_sale' && level < 4);
     (inferredByReservation ? inferredOnly : recorded).add(level);
    }
   }
   for (let level = 1; level <= 4; level++) {
    if (recorded.has(level) || inferredOnly.has(level)) counts[level]++;
    if (!recorded.has(level) && inferredOnly.has(level)) inferred[level]++;
   }
   continue;
  }
  const hasVisitRecord = events.some(e => ['visit_scheduled', 'visit_cancelled', 'visit'].includes(e.source));
  for (const e of events) {
   if (e.source === 'visit_cancelled') continue;
   if (e.source === 'reservation_rule' || e.source === 'reservation_sale') inferredStages.add(3);
   if (e.source !== 'reservation_rule') direct.add(e.level);
   if (e.level === 2) direct.add(1);
  }
  if (!hasVisitRecord && (direct.has(3) || inferredStages.has(3))) {
   inferredStages.add(1);
   inferredStages.add(2);
  }
  for (let level = 1; level <= 4; level++) {
   if (direct.has(level) || inferredStages.has(level)) counts[level]++;
   if (!direct.has(level) && inferredStages.has(level)) inferred[level]++;
  }
 }return {stages:['Prospect','Agendamento','Visita','Análise de Crédito','Venda Realizada'].map((label,i)=>({label,value:counts[i],inferred:inferred[i]})),returns};}
const api={current,sales,cohort};root.LcmLeadsFunnels=api;if(typeof module!=='undefined')module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:window);
