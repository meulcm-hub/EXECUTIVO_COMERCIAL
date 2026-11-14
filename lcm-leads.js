/* Gestão de Leads LCM: exclusivamente dados agregados de coortes CV CRM. */
(()=>{
'use strict';
const $=id=>document.getElementById(id);
const projects={
 'residencial flores do cerrado jacaranda':'Jacarandá',
 'residencial village lagoas':'Village Lagoas',
 'spe arraial costa verde club':'Arraial Costa Verde',
 'residencial jatoba':'Jatobá',
 'residencial extrema meu lar':'Extrema Meu Lar',
 'residencial flores do cerrado ipe':'Ipê',
 'residencial flamboyant':'Flamboyant',
 'residencial green plaza':'Green Plaza',
 'residencial terra solis':'Terra Solis',
 'spe arraial costa verde':'Arraial Costa Verde',
 'residencial santa catarina':'Santa Catarina',
 'residencial terra mater':'Terra Mater',
 'residencial turquesa parque':'Turquesa Parque',
 'residencial monttebelo':'Monttebelo',
 'sem empreendimento':'SEM EMPREENDIMENTO'};
const CV_ORIGINS={
 AP:'Aplicativo',AT:'Módulo de Atendimento',BC:'Busca Compartilhada',BO:'Busca Orgânica',
 CH:'Chat Online',CB:'ChatBot',DP:'Display',EM:'Email',FB:'Facebook',GO:'Google',
 IT:'InstaPage',IG:'Instagram',LI:'Ligação',MP:'Mídia Paga',OP:'Outras publicidades',
 CL:'Painel Cliente',CO:'Painel Corretor',GE:'Painel Gestor',IM:'Painel Imobiliária',
 PV:'Painel PDV',PT:'Phonetrack',PO:'Portais',RF:'Referência',SC:'Social',
 TD:'Tráfego Direto',TW:'Twitter',SI:'WebSite',UK:'Desconhecido',
 ND:'Não Definido',VO:'Vendas Online',RM:'Remarketing',PR:'Pinterest',
 TT:'Tik Tok',CV:'CVCRM',WA:'Whatsapp',OU:'Outros'
};
function originName(code){
 if(!code||code==='NÃO INFORMADA')return 'Não informada';
 return CV_ORIGINS[code]||(/^[A-Z]{1,3}$/.test(code)?'Origem '+code+' (sem descrição oficial)':code);
}
const NO_PROJECT='sem empreendimento';
function projectKey(raw){
 let x=String(raw??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().replace(/\s+/g,' ').toLowerCase();
 if(x==='residencial florres do cerrado ipe')x='residencial flores do cerrado ipe';
 if(!x||['null','undefined','não informado','nao informado','não identificado','nao identificado','sem vinculo','sem vínculo','sem empreendimento','-','--'].includes(x))return NO_PROJECT;
 return x;
}
function projectTitle(key){return projects[key]||key.replace(/\b\w/g,m=>m.toUpperCase());}
function projectKeys(){return [...new Set([...Object.keys(projects),...state.source.prospects.map(g=>projectKey(g.project))])];}

const steps=['Prospect','Agendamento','Visita','Análise de crédito','Venda concluída'];
const fmt=n=>new Intl.NumberFormat('pt-BR',{maximumFractionDigits:1}).format(n);
const dateValid=s=>/^\d{4}-\d{2}-\d{2}$/.test(s);
const iso=d=>d.toISOString().slice(0,10);
const parse=s=>new Date(s+'T12:00:00Z');
const days=(a,b)=>Math.round((parse(b)-parse(a))/86400000)+1;
const state={source:null,allHistory:null,groups:[],group:'month',filterStage:'all',
 selectedOrigins:new Set(),selectedVisitMedia:new Set()};
function txt(tag,text,cl){const node=document.createElement(tag);node.textContent=text;if(cl)node.className=cl;return node;}
function clear(id){const node=$(id);node.replaceChildren();return node;}
function makeOption(select,value,label){const x=document.createElement('option');x.value=value;x.textContent=label;select.append(x);}
function error(message){$('sourceState').textContent=message; $('scopeNote').textContent=message;}
function valid(payload){return payload?.validated===true&&payload.schema_version===2&&payload.classification_version===1&&
 payload.cohort_mode==='prospect_date'&&dateValid(payload.period?.since)&&dateValid(payload.period?.until)&&
 Array.isArray(payload.prospects)&&payload.prospects.every(g=>(g.project==null||typeof g.project==='string')&&Array.isArray(g.entries)&&
 g.entries.length>0&&typeof g.whatsapp_acquisition==='boolean'&&
 (g.new_date===null||dateValid(g.new_date))&&g.entries.every(e=>dateValid(e.date)&&Number.isInteger(e.stage)&&e.stage>=0&&e.stage<=4));}
function filters(){return {since:$('since').value,until:$('until').value,project:$('project').value,
 origins:state.selectedOrigins,visitMedia:state.selectedVisitMedia,stage:$('stage').value};}
function multiOptions(kind,values){
 const isOrigin=kind==='origin',selected=isOrigin?state.selectedOrigins:state.selectedVisitMedia;
 const container=$(isOrigin?'originOptions':'visitMediaOptions');
 const label=$(isOrigin?'originSummary':'visitMediaSummary');
 container.replaceChildren();
 if(!values.length){container.append(txt('p','A coleta integral ainda não está disponível. Os indicadores históricos continuam visíveis abaixo.','hint'));label.textContent=isOrigin?'Origens aguardando API':'Mídias aguardando API';return;}
 for(const value of values){
  const item=txt('label','','multi-check');const check=document.createElement('input');
  check.type='checkbox';check.value=value;check.checked=selected.has(value);
  const span=txt('span',isOrigin?originName(value):value);item.append(check,span);container.append(item);
  check.addEventListener('change',()=>{
   if(check.checked)selected.add(value);else selected.delete(value);
   multiLabel(kind);render();
  });
 }
 multiLabel(kind);
}
function multiLabel(kind){
 const selected=kind==='origin'?state.selectedOrigins:state.selectedVisitMedia;
 const el=$(kind==='origin'?'originSummary':'visitMediaSummary');
 el.textContent=selected.size?selected.size+' selecionada(s)':'Todas as '+(kind==='origin'?'origens':'mídias');
}
function selectedOnlyFromFull(){return state.selectedOrigins.size>0||state.selectedVisitMedia.size>0;}

function selected(f){
 if(!dateValid(f.since)||!dateValid(f.until)||f.since>f.until)return [];
 return state.source.prospects.flatMap((g,index)=>{
  const project=projectKey(g.project);
  if(f.project!=='all'&&project!==f.project)return [];
  const entries=g.entries.filter(e=>e.date>=f.since&&e.date<=f.until).sort((a,b)=>a.date.localeCompare(b.date));
  if(!entries.length)return [];
  const first=entries[0];
  // Etapa máxima a partir da entrada e ao longo da trajetória observada;
  // a mesma pessoa/empreendimento permanece uma única linha na seleção.
  if(f.stage!=='all'&&first.stage<Number(f.stage))return [];
  return [{project,whatsapp:g.whatsapp_acquisition,date:first.date,stage:first.stage,
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
function drawFullOpportunityFunnels(cells){
 const config=window.LcmLeadStages;
 if(!config)return;
 const cumulative=clear('opportunityCumulative');
 const empty=txt('p','O histórico completo de passagens por CAD/C e CAD/A ainda não foi extraído do CV CRM. Não é possível reconstruí-lo pela situação atual.','unavailable');
 cumulative.append(empty);
 const current=clear('opportunityCurrent');
 const counts=new Map(config.groups.map(group=>[group,0]));
 let unknown=0;
 for(const cell of cells){
  const group=config.classify(cell.status);
  if(group)counts.set(group,counts.get(group)+cell.count);
  else unknown+=cell.count;
 }
 const max=Math.max(1,...counts.values());
 for(const group of config.groups){
  const amount=counts.get(group);
  const line=txt('div','','opportunity-line opportunity-current');
  line.append(txt('span',group,'opportunity-name'));
  const slot=txt('div','','opportunity-slot');
  const bar=txt('div','','opportunity-bar');
  bar.style.width=(100*amount/max).toFixed(2)+'%';
  slot.append(bar);
  line.append(slot,txt('strong',fmt(amount)));
  current.append(line);
 }
 const total=cells.reduce((n,r)=>n+r.count,0);
 current.append(txt('p','Situação atual do CV CRM para leads cadastrados nas datas selecionadas, independentemente da origem. '+
 'Contagem: '+fmt(total)+' IDs únicos na seleção. '+
 (unknown?fmt(unknown)+' leads em outras situações (ex.: DESCARTADO), fora dos seis grupos; mantidos no total da base e não incluídos nas barras.':'Todos os registros foram classificados nos seis grupos.'),'hint'));
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
 for(const key of projectKeys()){
  const name=projectTitle(key);
  if($('project').value!=='all'&&$('project').value!==key)continue;
  const subset=rows.filter(r=>r.project===key),c=counts(subset),t=document.createElement('tr');
  [name,fmt(c.total),fmt(c.stages[2]),state.source.sales_link_validated?fmt(c.stages[4]):'—',state.source.sales_link_validated&&c.total?fmt(100*c.stages[4]/c.total)+'%':'—'].forEach(v=>t.append(txt('td',v)));
  body.append(t);
 }table.append(head,body);const wrap=txt('div','','tablewrap');wrap.append(table);host.append(wrap);
}
function insights(rows,c){
 const host=clear('insights');
 if(!rows.length){host.append(txt('p','Sem registros no recorte selecionado.'));return;}
 const grouped=projectKeys().map(key=>({name:projectTitle(key),count:rows.filter(r=>r.project===key).length})).sort((a,b)=>b.count-a.count);
 const high=grouped[0];
 host.append(txt('p','Maior volume no recorte: '+high.name+' · '+fmt(high.count)+' prospects ('+fmt(100*high.count/c.total)+'%).'));
 host.append(txt('p','Visitas alcançadas: '+fmt(c.stages[2])+' de '+fmt(c.total)+' prospects ('+fmt(100*c.stages[2]/c.total)+'%).'));
 host.append(txt('p','Sem dados de SDR, horários de primeira resposta ou últimos contatos: ranking de produtividade e alertas de SLA indisponíveis.'));
 host.append(txt('p','As contagens representam registros únicos por empreendimento na fonte anonimizada. Não comprovam unicidade de uma pessoa em empreendimentos distintos.'));
}
function filteredFullCells(){
 const source=state.allHistory;if(!source||!source.validated)return [];
 const f=filters();
 return source.by_registration_project_origin_status.filter(r=>
  r.date>=f.since&&r.date<=f.until&&
  (f.project==='all'||projectKey(r.project)===f.project)&&
  (!f.origins.size||f.origins.has(r.origin||'NÃO INFORMADA'))&&
  (!f.visitMedia.size||f.visitMedia.has(r.lead_media||'NÃO DISPONÍVEL NA COLETA ANTERIOR'))&&
  (f.stage==='all'||(f.stage==='FORA DO FUNIL'
   ?window.LcmLeadStages.classify(r.status)===null
   :window.LcmLeadStages.classify(r.status)===f.stage)));
}
function renderAllHistory(){
 const host=$('allKpis'),note=$('allSourceNote');
 if(!host||!note)return;
 host.replaceChildren();
 const source=state.allHistory;
 if(!source||!source.validated){
  note.textContent='A base integral com origem e mídia de visita ainda não está validada. A coleta será necessária para listar todas as opções reais. Não serão usados canais inventados.';
  clear('allProjects');clear('allOrigins');return;
 }
 const cells=filteredFullCells();
 const count=cells.reduce((sum,r)=>sum+r.count,0);
 const projectCounts=new Map(),originCounts=new Map(),mediaCounts=new Map();
 for(const row of cells){
  const project=projectTitle(projectKey(row.project));
  projectCounts.set(project,(projectCounts.get(project)||0)+row.count);
  const origin=originName(row.origin_name||row.origin||'NÃO INFORMADA');
  originCounts.set(origin,(originCounts.get(origin)||0)+row.count);
  const media=row.lead_media||'NÃO DISPONÍVEL NA COLETA ANTERIOR';
  mediaCounts.set(media,(mediaCounts.get(media)||0)+row.count);
 }
 putKpi(host,'Leads únicos filtrados',fmt(count),'Cadastro original; todas as origens');
 putKpi(host,'Empreendimentos filtrados',fmt(projectCounts.size),'Inclui SEM EMPREENDIMENTO');
 putKpi(host,'Origens no recorte',fmt(originCounts.size),'Seleção múltipla aplicada');
 putKpi(host,'Sem empreendimento',fmt(projectCounts.get('SEM EMPREENDIMENTO')||0),'Dentro dos filtros selecionados');
 const unavailable=mediaCounts.get('NÃO DISPONÍVEL NA COLETA ANTERIOR')||0;
 note.textContent='Base integral CV CRM · '+fmt(source.pages_scanned)+' páginas · '+
  fmt(source.unique_leads)+' IDs únicos totais · primeiro cadastro '+source.earliest_cadastro+
  ' · referência '+source.as_of+'. Filtros de origem e mídia de visita aplicados somente a esta fonte integral.'+
  (unavailable?' A mídia do lead ainda não está presente na coleta publicada.':'');
 const sorted=map=>[...map.entries()].sort((a,b)=>b[1]-a[1]).slice(0,15)
  .map(([label,value])=>({label,value}));
 bars($('allProjects'),sorted(projectCounts));bars($('allOrigins'),sorted(originCounts));
}
async function loadAllHistory(){
 try{
  const response=await fetch('data/leads-all-summary.json?v=full-history-v1',{cache:'no-store'});
  if(!response.ok)throw new Error('Ainda não publicado');
  const data=await response.json();
  if(![1,2,3].includes(data?.schema_version)||data.validated!==true||
    data.scope!=='all_accessible_leads'||!Array.isArray(data.by_registration_project_origin_status)||
    data.by_registration_project_origin_status.some(r=>typeof r.origin!=='string'||
      (data.schema_version>=2&&typeof r.visit_media!=='string')||
      (data.schema_version===3&&(typeof r.origin_name!=='string'||typeof r.lead_media!=='string')))||
    data.by_registration_project_origin_status.reduce((n,r)=>n+Number(r.count||0),0)!==data.unique_leads)
    throw new Error('Resumo integral sem validação');
  // Compatibilidade com os 78.644 leads já publicados no contrato v1:
  // campo de mídia de visita ainda não existe, portanto permanece desconhecido.
  state.allHistory=data.schema_version<3?{
   ...data,
   by_registration_project_origin_status:data.by_registration_project_origin_status.map(r=>({
    ...r,origin_name:r.origin_name||originName(r.origin),
    lead_media:'NÃO DISPONÍVEL NA COLETA ANTERIOR',
    visit_media:r.visit_media||'NÃO DISPONÍVEL NA API'
   }))
  }:data;
  const projectSelect=$('project'),selected=projectSelect.value;
  const keys=[...new Set(state.allHistory.by_registration_project_origin_status.map(r=>projectKey(r.project)))]
   .sort((a,b)=>projectTitle(a).localeCompare(projectTitle(b),'pt-BR'));
  projectSelect.replaceChildren();
  makeOption(projectSelect,'all','Todos os empreendimentos');
  for(const key of keys)makeOption(projectSelect,key,projectTitle(key));
  projectSelect.value=keys.includes(selected)?selected:'all';
  const stageSelect=$('stage');
  $('stageLabel').textContent='Situação atual / Etapa';
  stageSelect.replaceChildren();makeOption(stageSelect,'all','Todas as etapas');
  for(const group of window.LcmLeadStages.groups)makeOption(stageSelect,group,group);
  makeOption(stageSelect,'FORA DO FUNIL','Fora do funil / Descartado');
  stageSelect.value='all';
  const origins=[...new Set(state.allHistory.by_registration_project_origin_status.map(r=>r.origin||'NÃO INFORMADA'))].sort((a,b)=>originName(a).localeCompare(originName(b),'pt-BR'));
  const media=[...new Set(state.allHistory.by_registration_project_origin_status.map(r=>r.visit_media||'NÃO DISPONÍVEL NA API'))].sort((a,b)=>a.localeCompare(b,'pt-BR'));
  multiOptions('origin',origins);
  if(data.schema_version<3){
   multiOptions('visitMedia',[]);
   $('visitMediaSummary').textContent='Aguardando nova coleta';
   $('visitMediaDetails').open=false;
   $('visitMediaDetails').style.pointerEvents='none';
   $('visitMediaSummary').setAttribute('aria-disabled','true');
  }else{
   $('visitMediaDetails').style.pointerEvents='';
   $('visitMediaSummary').removeAttribute('aria-disabled');
   const realMedia=[...new Set(state.allHistory.by_registration_project_origin_status.map(r=>r.lead_media||'NÃO INFORMADA'))].sort((a,b)=>a.localeCompare(b,'pt-BR'));
   multiOptions('visitMedia',realMedia);
  }
  $('since').min=data.earliest_cadastro;$('until').min=data.earliest_cadastro;
  $('since').max=data.as_of;$('until').max=data.as_of;
  // Fonte integral validada: iniciar no primeiro cadastro efetivo do CV CRM.
  $('since').value=data.earliest_cadastro;
  $('until').value=data.as_of;
  $('sourceState').textContent='CV CRM · base integral '+data.as_of;
  render();
 }catch(e){
  state.allHistory=null;
  state.selectedOrigins.clear();state.selectedVisitMedia.clear();
  multiOptions('origin',[]);multiOptions('visitMedia',[]);
  $('originDetails').open=false;$('visitMediaDetails').open=false;
  render();
 }
}
function render(){
 if(!state.source)return;
 const requested=filters();
 if(!dateValid(requested.since)||!dateValid(requested.until)||requested.since>requested.until){
  $('scopeNote').textContent='Corrija as datas do período: início não pode ser posterior ao fim.';
  return;
 }
 renderAllHistory();
 const full=state.allHistory?.validated===true;
 const ids=['visao','funil','origens','evolucao'];
 if(full){
  for(const id of ids){const el=$(id);if(el)el.hidden=id!=='funil';}
  const cells=filteredFullCells();
  drawFullOpportunityFunnels(cells);
  const count=cells.reduce((n,r)=>n+r.count,0);
  $('scopeNote').textContent='Visão de oportunidades da base integral: '+fmt(count)+' leads cadastrados entre '+
   requested.since+' e '+requested.until+'. A situação corresponde ao último snapshot disponível, não ao estado histórico da época.';
  return;
 }
 const since=state.source.period.since,until=state.source.period.until;
 const knownProject=requested.project==='all'||state.source.prospects.some(g=>projectKey(g.project)===requested.project);
 const hasOverlap=requested.since<=until&&requested.until>=since;
 if(!knownProject||!hasOverlap){
  for(const id of ids){const el=$(id);if(el)el.hidden=true;}
  $('scopeNote').textContent=!knownProject
   ?'Sem dados disponíveis para '+projectTitle(requested.project)+' na fonte parcial do funil. Isso NÃO significa zero leads. A contagem depende da coleta integral do CV CRM.'
   :'Nenhum dado disponível na coorte parcial para o período '+requested.since+' a '+requested.until+
    '. Isso NÃO significa zero leads: a coleta integral histórica ainda não foi validada.';
  return;
 }
 for(const id of ids){const el=$(id);if(el)el.hidden=false;}
 const overlap={...requested,since:requested.since<since?since:requested.since,
   until:requested.until>until?until:requested.until};
 const rows=selected(overlap),c=counts(rows);state.groups=rows;
 $('scopeNote').textContent='Fonte PARCIAL de Marketing: '+fmt(c.total)+' grupos de lead/empreendimento, '+
  'cobertura '+overlap.since+' a '+overlap.until+'. '+
  (requested.since<since||requested.until>until?'O intervalo escolhido ultrapassa a cobertura; números anteriores a 2026 NÃO foram contabilizados. ':'')+
  'Para todas as origens, empreendimentos e datas, falta concluir a base integral do CV CRM.';
 drawKpis(overlap,rows,c);drawOpportunityFunnels(rows,c);drawOrigins(rows,c);
 drawTrend(rows);drawProjects(rows);insights(rows,c);
}

function csv(){
 const f=filters();
 let output;
 if(state.allHistory?.validated){
  const cells=filteredFullCells(),summary=new Map();
  for(const r of cells){
   const key=JSON.stringify([projectTitle(projectKey(r.project)),originName(r.origin_name||r.origin||'NÃO INFORMADA'),
    r.lead_media||'NÃO DISPONÍVEL NA COLETA ANTERIOR',r.status||'NÃO INFORMADA']);
   summary.set(key,(summary.get(key)||0)+r.count);
  }
  const rows=[['Empreendimento','Origem','Mídia de Visita','Situação Atual','Leads Únicos']];
  for(const [key,qty]of summary){rows.push([...JSON.parse(key),qty]);}
  output=rows;
 }else{
  if(!state.source)return;
  const overlap={...f,since:f.since<state.source.period.since?state.source.period.since:f.since,
   until:f.until>state.source.period.until?state.source.period.until:f.until};
  if(overlap.since>overlap.until){$('scopeNote').textContent='Sem dados para exportar nesta fonte parcial.';return;}
  const rows=selected(overlap),byProject=projectKeys().map(id=>{
   const name=projectTitle(id);
   const c=counts(rows.filter(r=>r.project===id));return [name,c.total,c.new,c.returns,c.whatsapp,...c.stages];
  });
  output=[['Empreendimento','Prospects','Novos','Retornos','WhatsApp FB',...steps],...byProject];
 }
 const result=output.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(';')).join('\r\n');
 const url=URL.createObjectURL(new Blob(['\ufeff'+result],{type:'text/csv;charset=utf-8'}));
 const a=document.createElement('a');a.href=url;
 a.download=state.allHistory?.validated?'LCM_Leads_Integral_Agregado.csv':'LCM_Leads_Coorte_Parcial.csv';
 a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

async function init(){
 try{
  const response=await fetch('data/cv-funnel.json?v=gestao-leads-v1',{cache:'no-store'});
  if(!response.ok)throw new Error('HTTP '+response.status);
  const payload=await response.json();
  if(!valid(payload))throw new Error('fonte CV CRM sem contrato validado');
  state.source=payload;
  $('since').value=payload.period.since;$('until').value=payload.period.until;
  for(const id of ['since','until']){$(id).min='1900-01-01';$(id).max=payload.as_of;}
  for(const key of projectKeys())makeOption($('project'),key,projectTitle(key));
  $('sourceState').textContent='CV CRM · coorte parcial '+payload.as_of;
  for(const id of ['since','until','project','stage'])$(id).addEventListener('change',render);
  $('reset').addEventListener('click',()=>{
   $('since').value=state.allHistory?.earliest_cadastro||payload.period.since;
   $('until').value=state.allHistory?.as_of||payload.period.until;
   $('project').value='all';$('stage').value='all';state.selectedOrigins.clear();state.selectedVisitMedia.clear();
   for(const kind of ['origin','visitMedia']){
    const container=$(kind==='origin'?'originOptions':'visitMediaOptions');
    container.querySelectorAll('input[type=checkbox]').forEach(el=>{el.checked=false;});
    multiLabel(kind);
   }
   render();
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
  await loadAllHistory();
 }catch(e){error('Fonte CV CRM indisponível: '+e.message);await loadAllHistory();}
}
init();
})();