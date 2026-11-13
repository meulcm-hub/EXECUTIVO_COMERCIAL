/* Inteligência Comercial LCM | V7. Agregados públicos; sem exposição de compradores. */
(()=>{
'use strict';
const host=document.getElementById('audience');
if(!host||host.dataset.intelligenceV4)return;
host.dataset.intelligenceV4='1';
const source=typeof AUD!=='undefined'?AUD:null;
const sales=typeof SALES!=='undefined'&&Array.isArray(SALES)?SALES:[];
if(!source){console.warn('Base do Público Comprador não disponível');return;}
const $=(id)=>document.getElementById(id);
const text=(tag,cls,value)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(value!==undefined)e.textContent=String(value);return e;};
const norm=x=>String(x||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toLowerCase();
const nf=n=>Number(n).toLocaleString('pt-BR',{maximumFractionDigits:1});
const money=n=>Number(n).toLocaleString('pt-BR',{style:'currency',currency:'BRL',maximumFractionDigits:0});
const valid=n=>Number.isFinite(Number(n))&&Number(n)>=0;
const categories=['Sexo','Faixa etária','Renda familiar','Estado civil','Profissão','Cidade','Bairro'];
const palette=['#94e85a','#1676a1','#9868cb','#e8a34c','#adc6d3','#48b5a4','#b1b6cb'];
const icon={
 overview:'▥',profile:'♙',origin:'⌖',ibge:'▦',compare:'▤',
 gender:'♙',age:'▣',income:'▤',civil:'♡',profession:'▧',cities:'⌖',district:'▦',insights:'✧'
};
const old={filters:host.querySelector('.filters'),kpis:$('audienceKpis'),charts:$('audienceCharts')};
const originalHint=host.querySelector('.muted.hint');
for(const el of [old.filters,old.kpis,old.charts,originalHint])if(el)el.classList.add('ci-original-hidden');
const mapStandby=text('div','ci-map-stage');
const ui=text('div','ci-app');
host.prepend(ui);
const header=text('header','ci-header');
const heading=text('div');
heading.append(text('h1','','♧  Público Comprador'),text('p','','Perfil, origem e comportamento dos compradores.'));
const headerButtons=text('div','ci-header-actions');
const exportBtn=text('button','ci-export','↓  Exportar PDF');
exportBtn.type='button';exportBtn.onclick=()=>window.print();headerButtons.append(text('span','ci-app-build','IBGE · V7'),exportBtn);
header.append(heading,headerButtons);ui.append(header);
const tabs=text('nav','ci-tabs');tabs.setAttribute('aria-label','Seções do Público Comprador');
const tabNames=[['overview','Visão Geral'],['profile','Perfil do Comprador'],['origin','Origem Geográfica'],['ibge','Potencial da Região (IBGE)'],['compare','Comparativo por Empreendimento']];
let currentTab='overview';
const panels={};
for(const [key,label] of tabNames){
 const btn=text('button','ci-tab',icon[key]+'  '+label);btn.type='button';btn.dataset.tab=key;
 btn.onclick=()=>showTab(key);
 tabs.append(btn);
 const panel=text('section','ci-view');panel.dataset.view=key;panel.setAttribute('aria-label',label);panels[key]=panel;
}
ui.append(tabs);
const filters=text('div','ci-filters');
function field(label,options){
 const wrapper=text('label','ci-filter');wrapper.append(text('span','',label));
 const select=document.createElement('select');for(const [v,l]of options){const o=new Option(l,v);select.add(o);}wrapper.append(select);filters.append(wrapper);return select;
}
const projects=Array.from(new Set([...Object.keys(source).filter(k=>k!=='Todos os empreendimentos'),'RESIDENCIAL TERRA SOLIS','RESIDENCIAL EXTREMA MEU LAR']));
const project=field('Empreendimento',[['','Todos os empreendimentos'],...projects.map(x=>[x,x])]);
const stages=[...new Set(sales.map(s=>norm(s.stage)==='etapa unica'?'Etapa única':String(s.stage||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'pt-BR'));
const years=[...new Set(sales.map(s=>String(s.date||'').slice(0,4)).filter(y=>/^20[0-9]{2}$/.test(y)))].sort().reverse();
const stage=field('Etapa da venda',[['','Todas as etapas'],...stages.map(x=>[x,x])]);
const origin=field('Imobiliária (origem da venda)',[['','Todas as imobiliárias']]);
const period=field('Período da venda',[['','Todo o histórico'],...years.map(x=>[x,x])]);
const scope=text('p','ci-data-note ci-filter-scope','Filtros de etapa, imobiliária e período aplicados somente aos registros de vendas. O perfil dos compradores e os dados IBGE não possuem vínculo individual para esse cruzamento.');
const apply=text('button','ci-filter-button','Filtrar');apply.type='button';apply.onclick=()=>render();
filters.append(apply,scope);ui.append(filters);
for(const [key]of tabNames)ui.append(panels[key]);
const foot=text('p','ci-data-note','Base de vendas: empreendimento, etapa, imobiliária e data disponíveis. Perfil demográfico: somente agregados por empreendimento. Imobiliária responsável não equivale à origem de captação do lead.');
ui.append(foot);
function refreshAgencies(){
 const prev=origin.value;
 const key=project.value;
 const names=[...new Set(sales.filter(s=>!key||norm(s.project)===norm(key)).map(s=>String(s.agency||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'pt-BR'));
 origin.replaceChildren(new Option('Todas as imobiliárias',''));
 for(const name of names)origin.add(new Option(name,name));
 if(names.includes(prev))origin.value=prev;
}
project.addEventListener('change',()=>{refreshAgencies();render();});
for(const control of [stage,origin,period])control.addEventListener('change',()=>render());
refreshAgencies();
function data(){return source[project.value||'Todos os empreendimentos']||{};}
function rows(o,key){return Array.isArray(o?.[key])?o[key].filter(x=>valid(x.count)&&Number(x.count)>0).map(x=>({label:String(x.label||'Não informado'),count:Number(x.count)})):[];}
function sum(arr){return arr.reduce((a,x)=>a+x.count,0);}
function panel(title,ico,desc){const p=text('article','ci-card');const h=text('div','ci-card-heading');h.append(text('span','ci-card-icon',icon[ico]||'◎'),text('h3','',title));p.append(h);if(desc)p.append(text('p','ci-card-sub',desc));return p;}
function nodeList(rows,max=8){
 const out=text('div','ci-bars'),total=sum(rows),largest=Math.max(1,...rows.map(x=>x.count));
 if(!total){out.append(text('p','ci-no-data','Sem informações classificadas para este empreendimento.'));return out;}
 for(const r of rows.slice(0,max)){const line=text('div','ci-bar-row');const label=text('span','ci-name',r.label),track=text('div','ci-track'),fill=text('span','ci-fill'),pct=text('strong','ci-percent',nf(r.count/total*100)+'%');
 fill.style.width=(r.count/largest*100)+'%';track.append(fill);line.append(label,track,pct);
 line.title=r.label+': '+nf(r.count)+' registros ('+nf(r.count/total*100)+'%)';line.setAttribute('aria-label',line.title);
 out.append(line);
 }
 return out;
}
function donut(rows,centerLabel){
 const out=text('div','ci-donut-layout'),total=sum(rows);
 if(!total){out.append(text('p','ci-no-data','Sem dados classificados.'));return out;}
 const chart=text('div','ci-donut');
 let cursor=0;const stops=rows.map((r,i)=>{const start=cursor;cursor+=r.count/total*100;return palette[i%palette.length]+' '+start+'% '+cursor+'%';});
 chart.style.background='conic-gradient('+stops.join(',')+')';
 const inner=text('div','ci-donut-inner');inner.append(text('b','',nf(total)),text('small','',centerLabel));chart.append(inner);
 const legend=text('div','ci-donut-legend');
 rows.forEach((r,i)=>{const item=text('div','ci-legend-row');const dot=text('i');dot.style.background=palette[i%palette.length];item.append(dot,text('span','',r.label),text('strong','',nf(r.count/total*100)+'%'));item.title=nf(r.count)+' registros';legend.append(item);});
 out.append(chart,legend);return out;
}
function metric(label,value,sub,ico){const p=text('div','ci-metric');p.append(text('span','ci-metric-icon',icon[ico]||'◈'));const box=text('div');box.append(text('small','',label),text('strong','',value),text('span','ci-metric-foot',sub));p.append(box);return p;}
function profileCard(o,key,ico,donutType=false){const arr=rows(o,key),p=panel(key==='Sexo'?'Gênero dos compradores':key,ico,'Quantidade e participação entre respostas classificadas');p.append(donutType?donut(arr,key==='Sexo'?'respostas':'registros'):nodeList(arr,key==='Profissão'?10:8));return p;}
function buildInsights(o){
 const p=text('section','ci-insights');p.append(text('h3','','✧  Principais insights'));
 const cards=text('div','ci-insight-list');
 for(const [key,verb]of [['Cidade','Maior origem municipal'],['Renda familiar','Faixa de renda predominante'],['Faixa etária','Faixa etária predominante']]){
  const items=rows(o,key).sort((a,b)=>b.count-a.count),d=text('div','ci-insight');
  d.append(text('b','',verb));d.append(text('span','',items.length?items[0].label+' · '+nf(items[0].count/sum(items)*100)+'% das respostas classificadas':'Sem dados suficientes'));cards.append(d);
 }
 p.append(cards);return p;
}
function salesFor(key){
 return sales.filter(s=>{
  if(key&&norm(s.project)!==norm(key))return false;
  if(stage.value&&norm(stage.value)!==norm(s.stage))return false;
  if(origin.value&&origin.value!==String(s.agency||'').trim())return false;
  if(period.value&&String(s.date||'').slice(0,4)!==period.value)return false;
  return Number.isFinite(Number(s.total))&&Number(s.total)>0;
 });
}
function activeSalesFilters(){return !!(stage.value||origin.value||period.value);}
function coverageNotice(){
 return 'Os filtros de etapa, imobiliária e período alteram exclusivamente indicadores da base de vendas. Perfis agregados e IBGE continuam por empreendimento.';
}
function overview(o){
 const wrap=panels.overview;wrap.replaceChildren();
 const sex=rows(o,'Sexo'),age=rows(o,'Faixa etária');
 const totalSex=sum(sex),totalAge=sum(age);
 const summary=text('div','ci-metrics');
 summary.append(
  metric('Compradores com gênero informado',totalSex?nf(totalSex):'—','Cobertura demográfica, não cadastro único','gender'),
  metric('Conversão de leads em vendas','—','Necessário funil de leads com vínculo validado','profile'),
  metric('Ticket médio de vendas',salesFor(project.value).length?money(salesFor(project.value).reduce((a,x)=>a+Number(x.total),0)/salesFor(project.value).length):'—','Base de vendas; período independente do perfil','income'),
  metric('Tempo médio de compra','—','Necessárias datas de entrada e venda por comprador','age')
 );
 wrap.append(summary);
 const validSales=salesFor(project.value);
 const saleCount=text('p','ci-quality','Vendas na seleção: '+nf(validSales.length)+'. '+(activeSalesFilters()?coverageNotice():'Dados do histórico de vendas, não equivalentes ao total de perfis demográficos.'));
 wrap.append(saleCount);
 if(totalSex!==totalAge){const warn=text('p','ci-quality','Atenção à cobertura: gênero '+nf(totalSex)+' registros; faixa etária '+nf(totalAge)+'. Não é correto apresentar esses totais como o mesmo universo de compradores.');wrap.append(warn);}
 const dem=text('div','ci-profile-grid');dem.append(
  profileCard(o,'Sexo','gender',true),profileCard(o,'Faixa etária','age'),profileCard(o,'Renda familiar','income'),profileCard(o,'Estado civil','civil',true));
 wrap.append(dem);
 const geo=text('div','ci-geo-grid');
 const map=panel('Origem dos compradores','cities','Mapa de localização aproximada; CEP, cidade ou bairro conforme a base confirmada');
 const mapAnchor=text('div','ci-map-anchor');mapAnchor.dataset.mapAnchor='overview';map.append(mapAnchor);
 const city=panel('Top 10 cidades','cities','Participação relativa por registros classificados'),hood=panel('Top 10 bairros','district','Participação relativa por registros classificados'),prof=profileCard(o,'Profissão','profession');
 city.append(nodeList(rows(o,'Cidade'),10));hood.append(nodeList(rows(o,'Bairro'),10));
 geo.append(map,hood,prof);map.classList.add('ci-geo-wide');
 wrap.append(geo,buildInsights(o));return mapAnchor;
}
function profile(o){
 const wrap=panels.profile;wrap.replaceChildren();
 if(activeSalesFilters())wrap.append(text('p','ci-quality',coverageNotice()));
 const grid=text('div','ci-profile-grid');grid.append(
  profileCard(o,'Sexo','gender',true),profileCard(o,'Faixa etária','age'),
  profileCard(o,'Renda familiar','income'),profileCard(o,'Estado civil','civil',true),
  profileCard(o,'Profissão','profession'));
 wrap.append(grid);
}
function geographic(o){
 const wrap=panels.origin;wrap.replaceChildren();
 if(activeSalesFilters())wrap.append(text('p','ci-quality',coverageNotice()));
 const lead=panel('Mapa de concentração dos compradores','cities','Coordenadas aproximadas, sem representar residências individuais');
 const slot=text('div','ci-map-anchor');slot.dataset.mapAnchor='origin';lead.append(slot);wrap.append(lead);
 const cards=text('div','ci-geo-rank');
 for(const [key,title]of [['Cidade','Top 10 cidades'],['Bairro','Top 10 bairros']]){const p=panel(title,key==='Cidade'?'cities':'district','Distribuição dos registros classificados');p.append(nodeList(rows(o,key),10));cards.append(p);}
 wrap.append(cards);
 const note=panel('Distância ao empreendimento','origin','Distâncias somente com geolocalização verificada da origem e endereço do empreendimento.');
 note.append(text('p','ci-no-data','Sem coordenadas verificadas dos empreendimentos nesta fonte. Nenhuma distância foi estimada.'));wrap.append(note);
}
// Demographic municipal context and site-level geospatial analysis are distinct layers.
let ibgeMunicipalitiesPromise=null;
const ibgeMunicipalCache=new Map();
function ibgeUf(m){
 return m?.microrregiao?.mesorregiao?.UF?.sigla||
  m?.["regiao-imediata"]?.["regiao-intermediaria"]?.UF?.sigla||"";
}
async function ibgeMunicipality(city,uf){
 if(!ibgeMunicipalitiesPromise){
  ibgeMunicipalitiesPromise=fetch("https://servicodados.ibge.gov.br/api/v1/localidades/municipios",{cache:"force-cache"})
   .then(r=>{if(!r.ok)throw Error("IBGE localidades indisponível");return r.json();})
   .catch(e=>{ibgeMunicipalitiesPromise=null;throw e;});
 }
 const places=await ibgeMunicipalitiesPromise;
 const matches=places.filter(m=>norm(m.nome)===norm(city)&&norm(ibgeUf(m))===norm(uf));
 if(matches.length!==1)throw Error("Município/UF sem correspondência inequívoca no IBGE");
 return matches[0];
}
async function ibgeMunicipalNumbers(m){
 if(!ibgeMunicipalCache.has(m.id)){
  const url="https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/variaveis/93%7C6318%7C614?localidades=N6%5B"+encodeURIComponent(m.id)+"%5D";
  const job=fetch(url,{cache:"force-cache"}).then(r=>{if(!r.ok)throw Error("IBGE agregados indisponível");return r.json();})
   .then(body=>{
    if(!Array.isArray(body))throw Error("Resposta IBGE inesperada");
    const values={};
    for(const item of body){
     const id=Number(item.id);
     const raw=item.resultados?.[0]?.series?.[0]?.serie?.["2022"];
     if([93,6318,614].includes(id)&&raw!=null&&String(raw).trim()!==""){
      const n=Number(raw);
      if(Number.isFinite(n)&&n>=0)values[id]=n;
     }
    }
    if(!Number.isFinite(values[93]))throw Error("População sem valor oficial válido");
    return values;
   }).catch(e=>{ibgeMunicipalCache.delete(m.id);throw e;});
  ibgeMunicipalCache.set(m.id,job);
 }
 return ibgeMunicipalCache.get(m.id);
}
function ibgeCard(label,value,subtitle){return metric(label,value,subtitle,"region");}
function ibgeAddressLine(p){
 const parts=[p.road,p.number,p.complement,p.district,p.city,p.state,p.postcode].filter(Boolean);
 return parts.join(" · ");
}

/* V7: section-specific UI; no changes to the original dashboard views. */
let opportunityMap=null, opportunityLayers=null, opportunityLeaflet=null;
const opportunityCache=new Map();
let opportunityPlanData=null;
const opportunitySourceUrls={
 census:"https://sidra.ibge.gov.br/tabela/4714",
 meta:"https://www.facebook.com/business/help",
 google:"https://support.google.com/adspolicy/answer/16701755?hl=pt-BR"
};
function opElem(tag,cls,content){
 const node=document.createElement(tag);if(cls)node.className=cls;
 if(content!==undefined)node.textContent=String(content);return node;
}
function opParagraph(textContent,cls="ci-op-note"){return opElem("p",cls,textContent);}
function opLine(title,desc){
 const line=opElem("div","ci-op-reason");line.append(opElem("strong","",title),opElem("span","",desc));return line;
}
function opValidCenter(p){
 const c=p?.center;
 return c?.source==="CV CRM"&&c.verified===true&&c.precision==="address_number"&&
 Number.isFinite(c.lat)&&Number.isFinite(c.lng)&&c.lat>=-34&&c.lat<=6&&c.lng>=-74&&c.lng<=-32;
}
function opValidRadii(d){
 return d&&d.year===2022&&d.method==="sector_intersection_area_weighted"&&
 Number.isFinite(d.population)&&d.population>=0&&Number.isFinite(d.households)&&d.households>=0;
}
async function opLoad(key,url,optional=false){
 if(!opportunityCache.has(key)){
  const promise=fetch(url,{cache:"force-cache"}).then(r=>{
   if(!r.ok)throw Error("Fonte indisponível ("+r.status+")");
   return r.json();
  }).catch(err=>{opportunityCache.delete(key);if(optional)return null;throw err;});
  opportunityCache.set(key,promise);
 }
 return opportunityCache.get(key);
}
function opAddress(a){
 if(!a)return "Endereço ainda não vinculado.";
 return [a.road,a.number,a.complement,a.district,a.city,a.state,a.postcode].filter(Boolean).join(" · ");
}
function opSource(tag,year,note){
 const p=opElem("div","ci-op-provenance");
 p.append(opElem("span","ci-op-tag",tag),opElem("span","",year),opElem("span","",note));return p;
}
function opKpi(name,value,unit,iconName,provenance){
 const p=opElem("article","ci-op-kpi");
 p.append(opElem("span","ci-op-kpi-icon",iconName));
 const content=opElem("div","ci-op-kpi-content");
 content.append(opElem("h3","",name),opElem("strong","",value),opElem("small","",unit));
 p.append(content);p.append(opElem("span","ci-op-kpi-source",provenance));return p;
}
function opCard(title,iconName,description){
 const p=opElem("section","ci-op-card"),h=opElem("header","ci-op-card-title");
 h.append(opElem("span","ci-op-icon",iconName),opElem("h3","",title));
 p.append(h);if(description)p.append(opParagraph(description,"ci-op-subtitle"));return p;
}
function opFilter(label,options,onChange){
 const outer=opElem("label","ci-op-filter");outer.append(opElem("span","",label));
 const select=document.createElement("select");
 for(const [key,val]of options)select.add(new Option(val,key));
 select.addEventListener("change",onChange);outer.append(select);return {outer,select};
}
function opRange(a,category){
 const r=rows(a,category).sort((a,b)=>b.count-a.count);
 return {rows:r,total:sum(r)};
}
function opMarkdownPlan(context){
 const {site,radius,municipality,publicTotal,buyerRows,regionStatus,market}=context;
 const name=site?.project||project.value;
 const top=buyerRows.length?buyerRows[0].label+" ("+nf(100*buyerRows[0].count/sum(buyerRows))+"% das respostas de renda)":"Renda não classificada";
 const lines=[
 "PLANO DE CAMPANHA — COMERCIAL LCM",
 "Empreendimento: "+name,
 "Cidade / UF: "+(site?.city||"Não informada")+"/"+(site?.state||"—"),
 "Endereço de referência: "+opAddress(site),
 "Raio de estudo solicitado: "+radius+" km",
 "FONTES E COBERTURA",
 "Público Comprador: agregados do CV CRM/planilha. Renda predominante: "+top+".",
 "Município IBGE: "+(municipality?("população municipal "+nf(municipality.population)+" (Censo 2022)."):"indicadores oficiais indisponíveis na consulta."),
 "Entorno setorial: "+regionStatus+".",
 "Potencial de mercado estimado: "+(market==null?"indisponível — não há base territorial e premissas auditadas.":nf(market)+" domicílios, metodologia setorial descrita na base."),
 "META ADS / FACEBOOK E INSTAGRAM",
 "Objetivo sugerido: captação de cadastros com formulário e WhatsApp, mediante aprovação do time comercial.",
 "Criativos: vídeos reais do empreendimento; tour, localização, condições comerciais confirmadas e CTA 'Conheça o empreendimento'.",
 "Geografia: testar município e entorno apenas onde a política de anúncios habitacionais permitir; sem excluir bairros por renda ou perfis demográficos.",
 "Métricas: gasto, contatos identificados, custo por lead válido, visitas e vendas atribuídas com IDs auditados.",
 "GOOGLE ADS / PESQUISA E YOUTUBE",
 "Objetivo sugerido: pesquisas de alta intenção sobre imóveis e apartamentos na cidade, com anúncios e páginas específicas do empreendimento.",
 "Ideias de busca: apartamento à venda em "+(site?.city||"sua cidade")+"; imóveis em "+(site?.city||"sua cidade")+"; "+name+".",
 "Criativos de vídeo: apresentação real do empreendimento e localização; evitar promessas não comprovadas.",
 "Página de destino: ficha do produto com mapa, fotos atualizadas, condições legais, formulário e medição de conversões.",
 "Métricas: termos de pesquisa, CTR, custo por lead válido, contatos qualificados, agendamentos e vendas auditadas.",
 "ORÇAMENTO E METAS",
 "Sem distribuição numérica automática: faltam CPA/ROI comparáveis e metas aprovadas do empreendimento.",
 "Testes A/B com objetivos, anúncios e públicos permitidos; avaliar qualidade de leads sem segmentação discriminatória.",
 "ALERTAS",
 "Não usar idade, gênero, raça, estado civil, renda individual ou atributos protegidos como critério discriminatório em anúncios de habitação.",
 "Não enviar contatos e dados de clientes a plataformas de anúncios a partir deste dashboard.",
 "Base publicitária Meta disponível no módulo Marketing, mas o vínculo empreendimento-campanha ainda requer validação; Google Ads não está integrado.",
 "Gerado em: "+new Date().toLocaleString("pt-BR")
 ];
 return lines.join("\n\n");
}
function opOpenPlan(plan){
 document.getElementById("ci-op-plan-overlay")?.remove();
 const overlay=opElem("div","ci-op-plan-overlay");overlay.id="ci-op-plan-overlay";
 overlay.setAttribute("role","dialog");overlay.setAttribute("aria-modal","true");
 const paper=opElem("div","ci-op-plan-paper");
 const actions=opElem("div","ci-op-plan-actions");
 const close=opElem("button","ci-op-btn","Fechar");close.type="button";
 close.onclick=()=>overlay.remove();
 const print=opElem("button","ci-op-btn ci-op-primary","Salvar plano em PDF");
 print.type="button";print.onclick=()=>window.print();
 actions.append(close,print);
 const title=opElem("h2","","Plano de campanha — Inteligência Comercial LCM");
 const body=opElem("pre","ci-op-plan-text",plan);
 paper.append(actions,title,body);overlay.append(paper);document.body.append(overlay);
 close.focus();
 overlay.addEventListener("click",e=>{if(e.target===overlay)overlay.remove();});
}
async function opLoadLeaflet(){
 if(window.L?.map)return window.L;
 if(window.__lcmOpportunityLeafletLoading)return window.__lcmOpportunityLeafletLoading;
 window.__lcmOpportunityLeafletLoading=new Promise((resolve,reject)=>{
  const css=document.querySelector('link[href*="leaflet.css"]');
  if(!css){const link=document.createElement("link");link.rel="stylesheet";link.href="vendor/leaflet/leaflet.css";document.head.append(link);}
  const script=document.createElement("script");script.src="vendor/leaflet/leaflet.js";
  script.onload=()=>window.L?.map?resolve(window.L):reject(Error("Leaflet inválido"));
  script.onerror=()=>reject(Error("Falha no Leaflet"));document.head.append(script);
 }).catch(e=>{window.__lcmOpportunityLeafletLoading=null;throw e;});
 return window.__lcmOpportunityLeafletLoading;
}
async function opDrawMap(container,options){
 if(opportunityMap){opportunityMap.remove();opportunityMap=null;}
 const L=await opLoadLeaflet();
 if(!container.isConnected||currentTab!=="ibge")return;
 const map=L.map(container,{scrollWheelZoom:false,zoomControl:true}).setView([-14.2,-51.9],4);
 opportunityMap=map;
 L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{
  maxZoom:19,attribution:'&copy; OpenStreetMap contributors'
 }).addTo(map);
 const cityLayer=L.layerGroup().addTo(map),districtLayer=L.layerGroup().addTo(map);
 const sectorLayer=L.geoJSON(null,{style:f=>({color:"#a4ef66",weight:1,fillColor:"#94d05f",fillOpacity:.2})}).addTo(map);
 const parcelLayer=L.layerGroup().addTo(map);
 opportunityLayers={cityLayer,districtLayer,sectorLayer,parcelLayer};
 const bounds=[];
 const buyerData=options.buyers;
 const allRows=(buyerData?.schema_version===1?buyerData:{"cities":[],"neighborhoods":[]});
 const valid=(r)=>r&&norm(r.project)===norm(options.name)&&Number.isFinite(r.lat)&&Number.isFinite(r.lng)&&r.count>=5;
 for(const pt of (allRows.cities||[]).filter(valid).filter(x=>!options.city||norm(x.city)===norm(options.city))){
  const mark=L.circleMarker([pt.lat,pt.lng],{radius:Math.min(28,6+Math.sqrt(pt.count)*1.45),color:"#92fa5f",fillColor:"#7bf35b",fillOpacity:.4,weight:2});
  mark.bindPopup(pt.city+" / "+pt.uf+" — "+nf(pt.count)+" compradores agregados (centro municipal, não endereço)");mark.addTo(cityLayer);
  bounds.push([pt.lat,pt.lng]);
 }
 for(const pt of (allRows.neighborhoods||[]).filter(valid).filter(x=>(!options.city||norm(x.city)===norm(options.city))&&(!options.district||norm(x.neighborhood)===norm(options.district)))){
  const mark=L.circleMarker([pt.lat,pt.lng],{radius:Math.min(22,4+Math.sqrt(pt.count)*1.5),color:"#4ac5f2",fillColor:"#38bcf1",fillOpacity:.5,weight:1});
  mark.bindPopup((pt.neighborhood||"Bairro")+" — "+nf(pt.count)+" compradores agregados (ponto aproximado)");mark.addTo(districtLayer);
  bounds.push([pt.lat,pt.lng]);
 }
 const region=options.region;
 if(region&&region.type==="FeatureCollection"&&region.metadata?.source==="IBGE"&&region.metadata?.year===2022&&
    Array.isArray(region.features)&&region.features.length<4000&&region.features.every(f=>f.geometry&&f.properties?.ibge_sector_code)){
  try{sectorLayer.addData(region);if(sectorLayer.getLayers().length)bounds.push(...[sectorLayer.getBounds().getSouthWest(),sectorLayer.getBounds().getNorthEast()].map(p=>[p.lat,p.lng]));}catch(_){}
 }
 if(opValidCenter(options.context)){
  const c=options.context.center;
  L.marker([c.lat,c.lng]).bindPopup("Localização verificada: "+options.name).addTo(parcelLayer);
  L.circle([c.lat,c.lng],{radius:options.radius*1000,color:"#a4fa63",weight:2,fillOpacity:.04,dashArray:"5 5"}).addTo(parcelLayer);
  bounds.push([c.lat,c.lng]);
 }
 if(bounds.length){map.fitBounds(bounds,{padding:[24,24],maxZoom:13});}
 const toggles=options.toggleContainer; 
 const controls=[
  ["Compradores por cidade",cityLayer,true],
  ["Compradores por bairro",districtLayer,false],
  ["Setores IBGE (quando disponíveis)",sectorLayer,true],
  ["Empreendimento e raio verificados",parcelLayer,true]
 ];
 for(const [label,layer,active]of controls){
  const lab=opElem("label","ci-op-layer");
  const ck=document.createElement("input");ck.type="checkbox";ck.checked=active;
  if(!active)map.removeLayer(layer);
  ck.onchange=()=>ck.checked?layer.addTo(map):map.removeLayer(layer);
  lab.append(ck,opElem("span","",label));toggles.append(lab);
 }
 requestAnimationFrame(()=>{if(container.isConnected)map.invalidateSize();});
}
async function ibge(o){
 const view=panels.ibge;view.replaceChildren();
 const ticket=++ibgeSession;
 if(opportunityMap){opportunityMap.remove();opportunityMap=null;}
 const outer=opElem("div","ci-op-v7");view.append(outer);
 const header=opElem("div","ci-op-section-lead");
 header.append(opElem("span","ci-op-eyebrow","INTELIGÊNCIA DE MERCADO · CENSO 2022"),opElem("h2","","Potencial da Região"),opParagraph("Perfil de compradores, contexto territorial e planejamento de campanhas por empreendimento."));
 outer.append(header);
 const bar=opElem("div","ci-op-toolbar");
 const projectsOptions=[["","Selecione o empreendimento"],...projects.map(name=>[name,name])];
 const projectF=opFilter("Empreendimento",projectsOptions,()=>{project.value=projectF.select.value;render();});
 projectF.select.value=project.value;bar.append(projectF.outer);
 const radiusF=opFilter("Raio de análise",[[1,"1 km"],[3,"3 km"],[5,"5 km"],[10,"10 km"]],()=>draw());
 radiusF.select.value="5";bar.append(radiusF.outer);
 const cityF=opFilter("Cidade",[["","Todas as cidades"]],()=>draw());bar.append(cityF.outer);
 const districtF=opFilter("Bairro",[["","Todos os bairros"]],()=>draw());bar.append(districtF.outer);
 const apply=opElem("button","ci-op-btn ci-op-primary","⌕  Filtrar");apply.type="button";
 apply.onclick=()=>draw();bar.append(apply);outer.append(bar);
 const metricRow=opElem("div","ci-op-metrics");outer.append(metricRow);
 const mid=opElem("div","ci-op-split");
 const compare=opCard("Compradores LCM × Potencial da Região","▥","Comparação entre registros históricos LCM e população oficial, com universos e abrangências distintos.");
 const compareBody=opElem("div","ci-op-comparison");compare.append(compareBody);mid.append(compare);
 const mapCard=opCard("Mapa de Oportunidades","⌖","Localidades agregadas reais e camadas geográficas disponíveis.");
 const mapLabels=opElem("div","ci-op-layers"),mapCanvas=opElem("div","ci-op-map");
 mapCanvas.setAttribute("aria-label","Mapa interativo de oportunidades");mapCard.append(mapLabels,mapCanvas);
 const mapNote=opParagraph("Mapa do OpenStreetMap; sem ponto confirmado do terreno ou setores processados, o mapa mostra apenas compradores agregados por cidade/bairro.");
 mapCard.append(mapNote);mid.append(mapCard);outer.append(mid);
 const reco=opCard("Recomendações de Campanhas","◎","Estratégias de teste para Meta Ads e Google Ads com justificativas e políticas de anúncios habitacionais.");
 const recogrid=opElem("div","ci-op-reco-grid");reco.append(recogrid);outer.append(reco);
 const footer=opElem("div","ci-op-footer");
 const generate=opElem("button","ci-op-btn ci-op-primary ci-op-generate","✦  Gerar plano de campanha completo");
 generate.type="button";generate.onclick=()=>{if(opportunityPlanData)opOpenPlan(opMarkdownPlan(opportunityPlanData));};
 footer.append(generate,opParagraph("Planejamento com fontes, motivos, limitações e opção de salvar em PDF."));outer.append(footer);
 const provenance=opElem("div","ci-op-data-footer");
 provenance.append(opSource("OFICIAL","IBGE · Censo 2022","População/área/densidade do município quando consultáveis."),
  opSource("INTERNO","LCM · perfil agregado","Categorias incompletas; coberturas diferentes."),
  opSource("PENDENTE","Setores, renda e domicílios por raio","Não inferir população ou elegibilidade do entorno."));
 outer.append(provenance);
 if(!project.value){
  metricRow.append(opParagraph("Selecione um empreendimento para consultar a região.","ci-op-empty"));
  compareBody.append(opParagraph("Selecione um empreendimento.","ci-op-empty"));
  return;
 }
 const addressTask=opLoad("addresses","config/ibge-project-addresses.json?v=v7");
 const buyersTask=opLoad("buyers","data/buyer-locations.json?v=v7",true);
 const contextTask=opLoad("geodata","data/ibge-project-context.json?v=v7",true);
 const sectorTask=opLoad("sector-map","data/ibge-opportunity-map.geojson?v=v7",true);
 const [addrResult,buyerResult,contextResult,sectorResult]=await Promise.allSettled([addressTask,buyersTask,contextTask,sectorTask]);
 if(ticket!==ibgeSession||currentTab!=="ibge")return;
 const addresses=addrResult.status==="fulfilled"?addrResult.value:null;
 const buyers=buyerResult.status==="fulfilled"?buyerResult.value:null;
 const contextData=contextResult.status==="fulfilled"?contextResult.value:null;
 const sectorData=sectorResult.status==="fulfilled"?sectorResult.value:null;
 const site=addresses?.projects?.find(p=>norm(p.project)===norm(project.value));
 const context=contextData?.projects?.find(p=>norm(p.project)===norm(project.value));
 const cityName=site?.city||"";
 const municipalPromise=site?ibgeMunicipality(site.city,site.state).then(m=>ibgeMunicipalNumbers(m).then(v=>({m,v}))):Promise.reject(Error("Sem município"));
 const municipal=await municipalPromise.catch(()=>null);
 if(ticket!==ibgeSession||currentTab!=="ibge")return;
 const cities=[...new Set([cityName,...(buyers?.cities||[]).filter(p=>norm(p.project)===norm(project.value)).map(p=>p.city)].filter(Boolean))].sort((a,b)=>a.localeCompare(b,"pt-BR"));
 for(const c of cities)cityF.select.add(new Option(c,c));
 cityF.select.value=cityName||"";
 let lastCity="";
 function refreshDistricts(){
  const value=cityF.select.value;
  if(lastCity===value)return;
  lastCity=value;
  districtF.select.replaceChildren(new Option("Todos os bairros",""));
  const named=(buyers?.neighborhoods||[]).filter(p=>norm(p.project)===norm(project.value)&&(!value||norm(p.city)===norm(value))).map(p=>p.neighborhood).filter(Boolean);
  for(const n of [...new Set(named)].sort((a,b)=>a.localeCompare(b,"pt-BR")))districtF.select.add(new Option(n,n));
 }
 cityF.select.addEventListener("change",()=>{refreshDistricts();draw();});
 refreshDistricts();
 function draw(){
  if(ticket!==ibgeSession||currentTab!=="ibge")return;
  const radius=Number(radiusF.select.value),city=cityF.select.value,district=districtF.select.value;
  const r=context?.radii?.[radius];
  const validRegion=opValidCenter(context)&&opValidRadii(r);
  const region=validRegion?r:null;
  const count=opRange(o,"Sexo").total;
  const salesSelection=salesFor(project.value);
  const moneyRows=opRange(o,"Renda familiar");
  let market=null;
  // Only published audited market potential with explicit methodology; do not calculate from population.
  if(validRegion&&Number.isFinite(r.marketPotential)&&r.marketPotential>=0&&r.marketMethod==="income_compatible_households_documented")market=r.marketPotential;
  metricRow.replaceChildren(
   opKpi("População (IBGE)",region?nf(region.population):municipal?nf(municipal.v[93]):"—",region?radius+" km · Censo 2022":"Município inteiro · Censo 2022","♧",region?"ESTIMATIVA SETORIAL":"IBGE MUNICIPAL"),
   opKpi("Domicílios",region?nf(region.households):"—",region?radius+" km · Censo 2022":"Base setorial por raio pendente","⌂",region?"ESTIMATIVA SETORIAL":"PENDENTE"),
   opKpi("Renda média domiciliar",region&&Number.isFinite(region.averageHouseholdIncome)?money(region.averageHouseholdIncome):"—",region&&Number.isFinite(region.averageHouseholdIncome)?"Censo 2022 · raio "+radius+" km":"Tabela de rendimento por setor pendente","▤",region?"FONTE VERIFICAR":"PENDENTE"),
   opKpi("Compradores LCM",count?nf(count):"—",count?"Registros classificados por gênero":"Sem cobertura de perfil nesta fonte","♙","LCM · HISTÓRICO"),
   opKpi("Potencial de mercado",market==null?"—":nf(market),market==null?"Modelo auditado ainda indisponível":"Domicílios compatíveis · hipótese documentada","◎",market==null?"PENDENTE":"ESTIMATIVA")
  );
  compareBody.replaceChildren();
  const tabs=opElem("div","ci-op-compare-tabs");
  const graph=opElem("div","ci-op-compare-body");
  const insights=opElem("aside","ci-op-insights");
  compareBody.append(tabs);
  const content=opElem("div","ci-op-compare-content");content.append(graph,insights);compareBody.append(content);
  const dimensionOpts=[["Renda familiar","Renda familiar"],["Faixa etária","Faixa etária"],["Cidade","Origem geográfica"],["Bairro","Bairros"]];
  let chosenDimension="Renda familiar";
  const insightRows=[];
  const cityData=opRange(o,"Cidade");
  if(cityData.total)insightRows.push(opLine("Origem observada",cityData.rows[0].label+" representa "+nf(100*cityData.rows[0].count/cityData.total)+"% das respostas classificadas por cidade."));
  if(moneyRows.total)insightRows.push(opLine("Perfil de renda histórico",moneyRows.rows[0].label+" é a maior categoria de renda declarada, com "+nf(100*moneyRows.rows[0].count/moneyRows.total)+"% das respostas."));
  if(municipal)insightRows.push(opLine("Escala do mercado",nf(municipal.v[93])+" habitantes em todo o município; isso não mede a população no raio nem potenciais compradores."));
  if(!validRegion)insightRows.push(opLine("Limite do cruzamento","Sem coordenadas e tabelas censitárias setoriais validadas, não há comparação quantitativa com renda ou idade do entorno."));
  if(!insightRows.length)insightRows.push(opLine("Dados insuficientes","Ainda não há agregados seguros para gerar um insight comparativo."));
  insights.append(opElem("h4","","✧  Insights do Cruzamento"),...insightRows);
  function drawGraph(){
   graph.replaceChildren();
   const ds=opRange(o,chosenDimension);
   if(!ds.total){graph.append(opParagraph("Sem respostas classificadas para esta dimensão.","ci-op-empty"));return;}
   const grid=opElem("div","ci-op-comparison-bars");
   for(const r of ds.rows.slice(0,7)){
    const line=opElem("div","ci-op-bar-line");line.append(opElem("span","ci-op-bar-name",r.label));
    const lane=opElem("div","ci-op-bar-track");const fill=opElem("div","ci-op-bar-fill");
    fill.style.width=Math.max(0,Math.min(100,100*r.count/ds.total))+"%";lane.append(fill);line.append(lane);
    line.append(opElem("b","",nf(r.count/ds.total*100)+"%"));grid.append(line);
   }
   graph.append(grid,opSource("LCM","Histórico","Percentual por categoria: "+nf(ds.total)+" respostas classificadas."));
   graph.append(opParagraph("Comparação IBGE: indisponível sem distribuição regional equivalente por setor e mesmo universo. Não foram criadas barras fictícias.","ci-op-warning"));
  }
  for(const [key,name]of dimensionOpts){
   const btn=opElem("button","ci-op-dim",name);btn.type="button";
   btn.onclick=()=>{chosenDimension=key;for(const b of tabs.children)b.classList.toggle("is-active",b===btn);drawGraph();};
   if(key===chosenDimension)btn.classList.add("is-active");tabs.append(btn);
  }
  drawGraph();
  mapLabels.replaceChildren();
  const cityInfo=city||site?.city||"cidade não identificada";
  mapNote.textContent=opValidCenter(context)
   ?"Mapa com coordenada verificada do empreendimento e agregados geográficos, quando disponíveis."
   :"Sem coordenada validada do empreendimento. Os pontos de compradores representam municípios/bairros aproximados, não um mapa de calor setorial nem endereço do terreno.";
  opDrawMap(mapCanvas,{name:project.value,city,district,radius,buyers,context,region:sectorData,toggleContainer:mapLabels}).catch(()=>{
   mapNote.textContent="Mapa indisponível no navegador; dados dos compradores continuam apresentados no painel comparativo.";
  });
  recogrid.replaceChildren();
  const campaignCity=site?.city||city||"município do empreendimento";
  function recCard(title,brand,items){
   const card=opElem("article","ci-op-campaign");
   const head=opElem("div","ci-op-campaign-head");head.append(opElem("span","ci-op-brand",brand),opElem("h4","",title),opElem("span","ci-op-pill","Recomendação, não resultado"));card.append(head);
   for(const [title,desc]of items)card.append(opLine(title,desc));
   return card;
  }
  recogrid.append(recCard("Meta Ads · Facebook e Instagram","f",[
    ["Objetivo","Teste de captação por formulário ou WhatsApp, com qualificação e registro de origem no CV CRM."],
    ["Criativos","Vídeo real da obra e unidades; diferenciais documentados, condições comerciais verificadas e tour do empreendimento."],
    ["Localização","Testar cobertura territorial permitida em "+campaignCity+"; sem excluir bairros com base em renda/perfil protegido."],
    ["Mensagem / CTA","“Conheça "+project.value+"” / “Fale com nossa equipe comercial”."],
    ["Medição","Gasto, contatos válidos, CPL válido, visitas e vendas com atribuição auditada."]
  ]),recCard("Google Ads · Pesquisa e YouTube","G",[
    ["Objetivo","Captar buscas de intenção de compra e ampliar reconhecimento com vídeo contextual."],
    ["Palavras-chave sugeridas","“apartamento à venda em "+campaignCity+"”, “imóveis em "+campaignCity+"”, nome do empreendimento."],
    ["Páginas de destino","Página específica com descrição, localização validada, fotos e formulário de contato."],
    ["Estratégia geográfica","Cidade e regiões permitidas pela plataforma, sem exclusões discriminatórias."],
    ["Medição","Termos de pesquisa, CTR, CPL válido, visitas, conversão e qualidade dos contatos."]
  ]));
  reco.append(opParagraph("Publicidade habitacional: validar categorias e regras aplicáveis no Meta e no Google. Não segmentar anúncios por idade, gênero, renda individual ou características protegidas. Sem orçamento automático sem dados comparáveis de ROI/CPL.","ci-op-warning"));
  opportunityPlanData={site:site||{project:project.value},radius,municipality:municipal?{population:municipal.v[93]}:null,publicTotal:count,buyerRows:moneyRows.rows,regionStatus:validRegion?"agregado de setores validado":"pendente de geocodificação setorial",market};
  generate.disabled=false;
 }
 draw();
}
let ibgeSession=0;
function compare(){
 const wrap=panels.compare;wrap.replaceChildren();
 const card=panel('Comparativo por empreendimento','compare','Cada percentual considera apenas os registros classificados na categoria analisada.');
 const scroll=text('div','ci-table-scroll'),table=text('table','ci-table');
 const head=text('thead'),tr=text('tr');
 for(const label of ['Empreendimento','Gênero informado','Faixa etária predominante','Renda predominante','Principal cidade','Ticket médio (vendas)'])tr.append(text('th','',label));
 head.append(tr);table.append(head);
 const body=text('tbody');
 for(const name of projects){
  const o=source[name]||{},r=text('tr');
  const first=k=>rows(o,k).sort((a,b)=>b.count-a.count)[0]?.label||'—';
  const arr=salesFor(name);const ticket=arr.length?money(arr.reduce((a,x)=>a+Number(x.total),0)/arr.length):'—';
  [name,nf(sum(rows(o,'Sexo'))),first('Faixa etária'),first('Renda familiar'),first('Cidade'),ticket].forEach(x=>r.append(text('td','',x)));
  body.append(r);
 }
 table.append(body);scroll.append(table);card.append(scroll);wrap.append(card);
 wrap.append(text('p','ci-data-note','Ticket médio respeita os filtros de etapa, imobiliária e período. Perfil de renda, idade e cidade é agregado histórico por empreendimento e não pode ser segmentado por esses filtros. Não há conversão de leads comparável nesta fonte.'));
}
function attachMap(){
 const map=$('lcmBuyerMap');if(!map)return;
 const target=panels[currentTab==='origin'?'origin':'overview'].querySelector('.ci-map-anchor');
 if(target&&map.parentElement!==target){target.append(map);map.classList.add('ci-owned-map');}
 if(target)setTimeout(()=>{map.lcmBuyerMap?.invalidateSize();map.lcmBuyerMap?.setProject(project.value);},150);
 if(currentTab!=='overview'&&currentTab!=='origin'){map.classList.add('ci-map-parked');}
 else map.classList.remove('ci-map-parked');
}
function showTab(key){
 currentTab=key;
 for(const [name,p]of Object.entries(panels))p.hidden=name!==key;
 for(const btn of tabs.querySelectorAll('button')){btn.classList.toggle('is-active',btn.dataset.tab===key);btn.setAttribute('aria-current',btn.dataset.tab===key?'page':'false');}
 if(key==='ibge')ibge(data());
 if(key==='compare')compare();
 attachMap();
}
function render(){
 const selected=project.value;
 if(old.filters?.querySelector('#audienceProject')){const original=old.filters.querySelector('#audienceProject');original.value=selected;original.dispatchEvent(new Event('change',{bubbles:true}));}
 const o=data();
 overview(o);profile(o);geographic(o);
 if(currentTab==='compare')compare();
 if(currentTab==='ibge')ibge(o);
 showTab(currentTab);
}
const observer=new MutationObserver(()=>{if($('lcmBuyerMap'))attachMap();});
observer.observe(host,{childList:true});
const jump=$('audienceMapJump');if(jump)jump.onclick=()=>{showTab('origin');panels.origin.scrollIntoView({behavior:'smooth'});};
render();
})();