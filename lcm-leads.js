/* Gestão de Leads LCM: exclusivamente dados agregados de coortes CV CRM. */
(()=>{
'use strict';
const $=id=>document.getElementById(id);
const projects={
 'residencial flores do cerrado jacaranda':'Jacarandá',
 'residencial village lagoas':'Village Lagoas',
 'spe arraial costa verde club':'Arraial Costa Verde',
 'residencial jatoba':'Jatobá'};
const steps=['Prospect','Agendamento','Visita','Análise de crédito','Venda concluída'];
const fmt=n=>new Intl.NumberFormat('pt-BR',{maximumFractionDigits:1}).format(n);
const dateValid=s=>/^\d{4}-\d{2}-\d{2}$/.test(s);
const iso=d=>d.toISOString().slice(0,10);
const parse=s=>new Date(s+'T12:00:00Z');
const days=(a,b)=>Math.round((parse(b)-parse(a))/86400000)+1;
const state={source:null,groups:[],group:'month',filterStage:'all'};
function txt(tag,text,cl){const node=document.createElement(tag);node.textContent=text;if(cl)node.className=cl;return node;}
function clear(id){const node=$(id);node.replaceChildren();return node;}
function makeOption(select,value,label){const x=document.createElement('option');x.value=value;x.textContent=label;select.append(x);}
function error(message){$('sourceState').textContent=message; $('scopeNote').textContent=message;}
function valid(payload){return payload?.validated===true&&payload.schema_version===2&&payload.classification_version===1&&
 payload.cohort_mode==='prospect_date'&&dateValid(payload.period?.since)&&dateValid(payload.period?.until)&&
 Array.isArray(payload.prospects)&&payload.prospects.every(g=>typeof g.project==='string'&&Array.isArray(g.entries)&&
 g.entries.length>0&&typeof g.whatsapp_acquisition==='boolean'&&
 (g.new_date===null||dateValid(g.new_date))&&g.entries.every(e=>dateValid(e.date)&&Number.isInteger(e.stage)&&e.stage>=0&&e.stage<=4));}
function filters(){return {since:$('since').value,until:$('until').value,project:$('project').value,origin:$('origin').value,stage:$('stage').value};}
function selected(f){
 if(!dateValid(f.since)||!dateValid(f.until)||f.since>f.until)return [];
 return state.source.prospects.flatMap((g,index)=>{
  if(f.project!=='all'&&g.project!==f.project)return [];
  if(f.origin==='whatsapp'&&!g.whatsapp_acquisition)return [];
  if(f.origin==='other'&&g.whatsapp_acquisition)return [];
  const entries=g.entries.filter(e=>e.date>=f.since&&e.date<=f.until).sort((a,b)=>a.date.localeCompare(b.date));
  if(!entries.length)return [];
  const first=entries[0];
  // Etapa máxima a partir da entrada e ao longo da trajetória observada;
  // a mesma pessoa/empreendimento permanece uma única linha na seleção.
  if(f.stage!=='all'&&first.stage<Number(f.stage))return [];
  return [{project:g.project,whatsapp:g.whatsapp_acquisition,date:first.date,stage:first.stage,
    isNew:g.new_date!==null&&g.new_date>=f.since&&g.new_date<=f.until,index}];
 });
}
function counts(rows){const stepsCount=steps.map((_,i)=>rows.filter(r=>r.stage>=i).length);return {total:rows.length,stages:stepsCount,new:rows.filter(r=>r.isNew).length,returns:rows.filter(r=>!r.isNew).length,whatsapp:rows.filter(r=>r.whatsapp).length};}
function periodComparison(f){const span=days(f.since,f.until);if(!Number.isFinite(span)||span<1)return null;
 const end=parse(f.since);end.setUTCDate(end.getUTCDate()-1);const start=new Date(end);start.setUTCDate(start.getUTCDate()-span+1);
 const p={...f,since:iso(start),until:iso(end)};
 if(p.since<state.source.period.since)return null;
 return counts(selected(p));
}
function putKpi(node,label,value,detail){const k=txt('article','','kpi');k.append(txt('small',label),txt('strong',value),txt('p',detail));node.append(k);}
function drawKpis(f,rows,c){
 const node=clear('kpis'),prev=periodComparison(f);
 const delta=prev?((c.total-prev.total)/Math.max(prev.total,1)*100):null;
 putKpi(node,'Prospects na safra',fmt(c.total),delta===null?'Sem período anterior com cobertura':'Variação vs. período anterior: '+(delta>=0?'+':'')+fmt(delta)+'%');
 putKpi(node,'Novos cadastros',fmt(c.new),'Data original dentro do período selecionado');
 putKpi(node,'Retornos adicionais',fmt(c.returns),'Entraram por conversão; não são novos cadastros');
 putKpi(node,'Entradas WhatsApp Facebook',fmt(c.whatsapp),'Flag de aquisição declarada no CV CRM');
 putKpi(node,'Agendamento alcançado',fmt(c.stages[1]),'Etapa cumulativa identificada na fonte');
 putKpi(node,'Visita alcançada',fmt(c.stages[2]),'Não equivale a atendimento inicial');
 putKpi(node,'Análise de crédito',fmt(c.stages[3]),'Etapa de pré-cadastro/análise validada');
 putKpi(node,'Vendas vinculadas',state.source.sales_link_validated?fmt(c.stages[4]):'—',
   state.source.sales_link_validated?'Taxa de conversão: '+(c.total?fmt(100*c.stages[4]/c.total):'0')+'%':'Vinculação de vendas em auditoria');
}
function drawOpportunityFunnels(rows,c){
 const config=window.LcmLeadStages;
 if(!config)throw new Error('Taxonomia de etapas indisponível');
 const cumulative=clear('opportunityCumulative');
 const historical={
  'AGENDAMENTO':c.stages[1],
  'VISITA':c.stages[2],
  'ANÁLISE DE CRÉDITO':c.stages[3],
  'VENDA REALIZADA':state.source.sales_link_validated?c.stages[4]:null
 };
 const verifiedMax=Math.max(1,...Object.values(historical).filter(Number.isFinite));
 for(const name of config.detailed){
  const amount=Object.prototype.hasOwnProperty.call(historical,name)?historical[name]:null;
  const line=txt('div','','opportunity-line');
  line.append(txt('span',name,'opportunity-name'));
  const slot=txt('div','','opportunity-slot');
  if(amount!==null&&Number.isFinite(amount)){
   const bar=txt('div','','opportunity-bar');
   bar.style.width=Math.max(2,100*amount/verifiedMax)+'%';
   slot.append(bar);
   line.append(slot,txt('strong',fmt(amount)));
  }else{
   slot.append(txt('div','Histórico não disponível','opportunity-missing'));
   line.append(slot,txt('strong','—'));
  }
  cumulative.append(line);
 }
 cumulative.append(txt('p','Apenas Agendamento, Visita, Análise e Venda usam as etapas já validadas no funil do Marketing. A coorte disponível não registra o histórico CAD/C e CAD/A nem engloba todas as origens; não é possível calcular perdas ou taxas entre essas 16 etapas.','hint'));
 const current=clear('opportunityCurrent');
 for(const name of config.groups){
  const line=txt('div','','opportunity-line opportunity-current');
  line.append(txt('span',name,'opportunity-name'));
  const slot=txt('div','','opportunity-slot');
  slot.append(txt('div','Aguardando situação atual do CV CRM','opportunity-missing'));
  line.append(slot,txt('strong','—'));
  current.append(line);
 }
 current.append(txt('p','O arquivo atual contém o estágio máximo de uma coorte, não a situação atual da oportunidade. Contagens e percentuais deste painel dependem de leitura de situações e IDs únicos das oportunidades, para todas as origens.','hint'));
}
function bars(node,items){node.replaceChildren();const max=Math.max(1,...items.map(x=>x.value));for(const item of items){
 const r=txt('div','','baritem');r.append(txt('span',item.label));const track=txt('div','','bar-track');
 const fill=txt('div','','bar-fill');fill.style.width=Math.max(0,item.value/max*100)+'%';track.append(fill);
 r.append(track,txt('strong',fmt(item.value)));node.append(r);
}}
function drawOrigins(rows,c){
 const node=$('origins');
 bars(node,[{label:'WhatsApp FB',value:c.whatsapp},{label:'Outras elegíveis',value:c.total-c.whatsapp}]);
 $('originLegend').textContent='Outras elegíveis = demais grupos do funil CV CRM que não possuem flag WhatsApp Facebook. Não é possível distinguir com segurança Facebook formulário, Google ou origem histórica nesta versão do arquivo.';
}
function groupKey(date){
 if(state.group==='day')return date;
 if(state.group==='month')return date.slice(0,7);
 const d=parse(date);const dow=(d.getUTCDay()+6)%7;d.setUTCDate(d.getUTCDate()-dow);return iso(d);
}
function drawTrend(rows){
 const c=new Map();
 for(const r of rows){const key=groupKey(r.date);c.set(key,(c.get(key)||0)+1);}
 const items=[...c.entries()].sort(([a],[b])=>a.localeCompare(b)).map(([label,value])=>({label,value}));
 const node=$('trend');
 if(items.length===0){node.replaceChildren(txt('p','Sem entradas neste recorte.','hint'));return;}
 const shortlist=items.length>50?items.slice(-50):items;bars(node,shortlist);
 if(items.length>50)node.prepend(txt('p','Exibindo os últimos 50 intervalos para preservar a legibilidade.','hint'));
}
function drawProjects(rows){
 const host=clear('projectTable'),table=document.createElement('table'),head=document.createElement('thead'),body=document.createElement('tbody');
 const tr=document.createElement('tr');
 ['Empreendimento','Prospects','Visita','Venda','Conversão'].forEach(x=>tr.append(txt('th',x)));head.append(tr);
 for(const [key,name] of Object.entries(projects)){
  if($('project').value!=='all'&&$('project').value!==key)continue;
  const subset=rows.filter(r=>r.project===key),c=counts(subset),t=document.createElement('tr');
  [name,fmt(c.total),fmt(c.stages[2]),state.source.sales_link_validated?fmt(c.stages[4]):'—',state.source.sales_link_validated&&c.total?fmt(100*c.stages[4]/c.total)+'%':'—'].forEach(v=>t.append(txt('td',v)));
  body.append(t);
 }table.append(head,body);const wrap=txt('div','','tablewrap');wrap.append(table);host.append(wrap);
}
function insights(rows,c){
 const host=clear('insights');
 if(!rows.length){host.append(txt('p','Sem registros no recorte selecionado.'));return;}
 const grouped=Object.entries(projects).map(([key,name])=>({name,count:rows.filter(r=>r.project===key).length})).sort((a,b)=>b.count-a.count);
 const high=grouped[0];
 host.append(txt('p','Maior volume no recorte: '+high.name+' · '+fmt(high.count)+' prospects ('+fmt(100*high.count/c.total)+'%).'));
 host.append(txt('p','Visitas alcançadas: '+fmt(c.stages[2])+' de '+fmt(c.total)+' prospects ('+fmt(100*c.stages[2]/c.total)+'%).'));
 host.append(txt('p','Sem dados de SDR, horários de primeira resposta ou últimos contatos: ranking de produtividade e alertas de SLA indisponíveis.'));
 host.append(txt('p','As contagens representam registros únicos por empreendimento na fonte anonimizada. Não comprovam unicidade de uma pessoa em empreendimentos distintos.'));
}
function render(){
 if(!state.source)return;
 const f=filters();
 if(!dateValid(f.since)||!dateValid(f.until)||f.since>f.until||f.since<state.source.period.since||f.until>state.source.period.until){
  $('scopeNote').textContent='Período inválido ou fora da cobertura CV CRM: '+state.source.period.since+' a '+state.source.period.until;
  return;
 }
 const rows=selected(f),c=counts(rows);state.groups=rows;
 $('scopeNote').textContent='Fonte CV CRM validada até '+state.source.as_of+' · '+fmt(c.total)+' grupos de lead/empreendimento na seleção. Período de entrada: '+f.since+' a '+f.until+'. Atenção: esta base reflete a coorte histórica de captação do funil (escopo anterior Facebook/Google), não os 100% dos leads do CV CRM. Não contém interações, SDRs nem identificação pessoal.';
 drawKpis(f,rows,c);drawOpportunityFunnels(rows,c);drawOrigins(rows,c);drawTrend(rows);drawProjects(rows);insights(rows,c);
}
function csv(){
 if(!state.source)return;
 const f=filters(),rows=selected(f),byProject=Object.entries(projects).map(([id,name])=>{
 const c=counts(rows.filter(r=>r.project===id));return [name,c.total,c.new,c.returns,c.whatsapp,...c.stages];});
 const output=[['Empreendimento','Prospects','Novos','Retornos','WhatsApp FB',...steps],...byProject]
   .map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(';')).join('\r\n');
 const url=URL.createObjectURL(new Blob(['\ufeff'+output],{type:'text/csv;charset=utf-8'}));
 const a=document.createElement('a');a.href=url;a.download='LCM_Gestao_Leads_Agregados.csv';a.click();
 setTimeout(()=>URL.revokeObjectURL(url),1000);
}
async function init(){
 try{
  const response=await fetch('data/cv-funnel.json?v=gestao-leads-v1',{cache:'no-store'});
  if(!response.ok)throw new Error('HTTP '+response.status);
  const payload=await response.json();
  if(!valid(payload))throw new Error('fonte CV CRM sem contrato validado');
  state.source=payload;
  $('since').value=payload.period.since;$('until').value=payload.period.until;
  for(const id of ['since','until']){$(id).min=payload.period.since;$(id).max=payload.period.until;}
  for(const [key,name]of Object.entries(projects))makeOption($('project'),key,name);
  $('sourceState').textContent='CV CRM · atualizado em '+payload.as_of;
  for(const id of ['since','until','project','origin','stage'])$(id).addEventListener('change',render);
  $('reset').addEventListener('click',()=>{
   $('since').value=payload.period.since;$('until').value=payload.period.until;
   $('project').value='all';$('origin').value='all';$('stage').value='all';render();
  });
  document.querySelectorAll('[data-group]').forEach(button=>{
   button.addEventListener('click',()=>{
    state.group=button.dataset.group;
    document.querySelectorAll('[data-group]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
    drawTrend(state.groups);
   });
   button.setAttribute('aria-pressed',String(button.dataset.group===state.group));
  });
  $('export').addEventListener('click',csv);
  render();
 }catch(e){error('Fonte CV CRM indisponível: '+e.message);}
}
init();
})();