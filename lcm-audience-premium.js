/* Inteligência Comercial LCM | V4. Agregados públicos; sem exposição de compradores. */
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
exportBtn.type='button';exportBtn.onclick=()=>window.print();headerButtons.append(exportBtn);
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
filters.append(scope);
const apply=text('button','ci-filter-button','Filtrar');apply.type='button';apply.onclick=()=>render();
filters.append(apply);ui.append(filters);
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
async function ibge(o){
 const wrap=panels.ibge;wrap.replaceChildren();
 const session=++ibgeSession;
 const selected=project.value;
 const top=panel("Endereço do empreendimento","region","Referência física informada pela LCM em 13/11/2026; pode precisar de confirmação do ponto exato do terreno.");
 wrap.append(top);
 if(!selected){
  top.append(text("p","ci-no-data","Selecione um empreendimento para visualizar seu endereço, indicadores do município e situação do estudo do entorno."));
  return;
 }
 const addressStatus=text("p","ci-no-data","Consultando cadastro de endereços confirmados…");
 top.append(addressStatus);
 const municipality=panel("Censo 2022 — panorama municipal","region","Dados oficiais para o município inteiro; não representam a população próxima à obra.");
 const numbers=text("div","ci-ibge-stats");
 numbers.append(text("p","ci-no-data","Carregando dados do IBGE…"));
 municipality.append(numbers);wrap.append(municipality);
 const radius=panel("Estudo do entorno do empreendimento","origin","Raio geográfico de 1, 3, 5 ou 10 km a partir do centro do terreno validado.");
 const status=text("p","ci-no-data","Verificando disponibilidade de setores censitários processados…");
 const radiusLabel=text("label","ci-filter","Raio de análise");
 const radiusSelect=document.createElement("select");
 for(const km of [1,3,5,10])radiusSelect.add(new Option(km+" km",String(km)));
 radiusSelect.value="3";radiusLabel.append(radiusSelect);
 radius.append(radiusLabel,status);wrap.append(radius);
 const sources=text("p","ci-data-note","Fonte de população, área e densidade municipal: IBGE, Censo Demográfico 2022, tabela SIDRA 4714. Para estudo por raio: malha e agregados de setores censitários de 2022. Números do município nunca são apresentados como números do raio.");
 wrap.append(sources);
 const official=text("a","ci-source-link","IBGE · Tabela 4714 e metadados");
 official.href="https://sidra.ibge.gov.br/tabela/4714";official.target="_blank";official.rel="noopener noreferrer";municipality.append(official);
 let address=null;
 try{
  const response=await fetch("config/ibge-project-addresses.json?v=20261113-2",{cache:"no-store"});
  if(!response.ok)throw Error("Cadastro de endereços indisponível");
  const data=await response.json();
  if(session!==ibgeSession||currentTab!=="ibge")return;
  address=data.projects?.find(x=>norm(x.project)===norm(selected));
  if(!address)throw Error("Empreendimento sem endereço confirmado nesta listagem");
  addressStatus.replaceChildren();
  addressStatus.append(text("strong","",ibgeAddressLine(address)||"Endereço ainda não informado"));
  if(address.same_reference_address_adjacent_distinct_sites){
   addressStatus.append(text("p","ci-data-note","Empreendimento em terreno distinto de seu vizinho, embora compartilhem o endereço de referência. O centro de cada terreno deverá ser validado separadamente."));
  }
  if(!address.road||!address.number){
   addressStatus.append(text("p","ci-data-note","Faltam informações suficientes para determinar a porta ou o centro do terreno; um endereço de referência não é uma coordenada exata."));
  }
 }catch(err){
  if(session===ibgeSession)addressStatus.textContent="Endereço não disponível no cadastro integrado. "+err.message;
  numbers.replaceChildren(text("p","ci-no-data","Sem município confirmado para consultar o Censo."));
  status.textContent="Sem localização aprovada para calcular a população por raio.";
  return;
 }
 async function drawRadius(){
  status.textContent="Sem cálculo setorial aprovado para este raio. O endereço informado não equivale automaticamente ao centro geográfico validado.";
  try{
   const response=await fetch("data/ibge-project-context.json?v=2",{cache:"no-store"});
   if(!response.ok)return;
   const data=await response.json();
   if(session!==ibgeSession||currentTab!=="ibge")return;
   const item=data.projects?.find(p=>norm(p.project)===norm(selected));
   const center=item?.center, chosen=item?.radii?.[radiusSelect.value];
   if(!(center?.source==="CV CRM"&&center?.verified===true&&center?.precision==="address_number"&&
        Number.isFinite(center.lat)&&Number.isFinite(center.lng))||!chosen)return;
   if(chosen.year!==2022||chosen.method!=="sector_intersection_area_weighted"||
      !Number.isFinite(chosen.population)||!Number.isFinite(chosen.households))return;
   status.replaceChildren();
   const cards=text("div","ci-ibge-stats");
   cards.append(ibgeCard("População estimada",nf(chosen.population),"Censo 2022 · raio "+radiusSelect.value+" km"),
     ibgeCard("Domicílios estimados",nf(chosen.households),"Censo 2022 · raio "+radiusSelect.value+" km"));
   if(Number.isFinite(chosen.populationDensity))cards.append(ibgeCard("Densidade estimada",nf(chosen.populationDensity),"hab./km² · raio "+radiusSelect.value+" km"));
   status.append(cards,text("p","ci-data-note","Estimativa de interseção espacial de setores censitários, sujeita à hipótese de distribuição uniforme da população dentro dos setores."));
  }catch(_){}
 }
 radiusSelect.addEventListener("change",drawRadius);
 drawRadius();
 try{
  const m=await ibgeMunicipality(address.city,address.state);
  if(session!==ibgeSession||currentTab!=="ibge")return;
  const v=await ibgeMunicipalNumbers(m);
  if(session!==ibgeSession||currentTab!=="ibge")return;
  numbers.replaceChildren(
   ibgeCard("População do município",nf(v[93]),m.nome+" / "+ibgeUf(m)+" · Censo 2022"),
   ibgeCard("Área municipal",Number.isFinite(v[6318])?nf(v[6318]):"—","km² · Censo 2022"),
   ibgeCard("Densidade municipal",Number.isFinite(v[614])?nf(v[614]):"—","hab./km² · Censo 2022")
  );
 }catch(err){
  if(session===ibgeSession){
   numbers.replaceChildren(text("p","ci-no-data","Não foi possível consultar o indicador municipal no IBGE agora. Verifique a disponibilidade da API oficial."));
  }
 }
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