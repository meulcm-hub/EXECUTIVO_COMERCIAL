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
const projects=Object.keys(source).filter(k=>k!=='Todos os empreendimentos');
const project=field('Empreendimento',[['','Todos os empreendimentos'],...projects.map(x=>[x,x])]);
const stage=field('Etapa',[['','Todas as etapas — sem vínculo demográfico']]);
const origin=field('Origem',[['','Todas as origens — sem vínculo por etapa']]);
const period=field('Período',[['','Base integral — sem datas individuais']]);
for(const sel of [stage,origin,period]){sel.disabled=true;sel.title='Esta fonte contém apenas agregados por empreendimento. Habilitar este filtro exigiria registros com vínculo de data, etapa e comprador.';}
const apply=text('button','ci-filter-button','Filtrar');apply.type='button';apply.onclick=()=>render();
filters.append(apply);ui.append(filters);
for(const [key]of tabNames)ui.append(panels[key]);
const foot=text('p','ci-data-note','As distribuições demográficas são agregadas e podem ter coberturas diferentes por categoria. Etapa, origem de captação e período exigem cruzamento validado com registros individuais; filtros indisponíveis até integração segura.');
ui.append(foot);
project.addEventListener('change',()=>render());
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
function salesFor(key){return sales.filter(s=>(!key||norm(s.project)===norm(key))&&Number.isFinite(Number(s.total))&&Number(s.total)>0);}
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
 const grid=text('div','ci-profile-grid');grid.append(
  profileCard(o,'Sexo','gender',true),profileCard(o,'Faixa etária','age'),
  profileCard(o,'Renda familiar','income'),profileCard(o,'Estado civil','civil',true),
  profileCard(o,'Profissão','profession'));
 wrap.append(grid);
}
function geographic(o){
 const wrap=panels.origin;wrap.replaceChildren();
 const lead=panel('Mapa de concentração dos compradores','cities','Coordenadas aproximadas, sem representar residências individuais');
 const slot=text('div','ci-map-anchor');slot.dataset.mapAnchor='origin';lead.append(slot);wrap.append(lead);
 const cards=text('div','ci-geo-rank');
 for(const [key,title]of [['Cidade','Top 10 cidades'],['Bairro','Top 10 bairros']]){const p=panel(title,key==='Cidade'?'cities':'district','Distribuição dos registros classificados');p.append(nodeList(rows(o,key),10));cards.append(p);}
 wrap.append(cards);
 const note=panel('Distância ao empreendimento','origin','Distâncias somente com geolocalização verificada da origem e endereço do empreendimento.');
 note.append(text('p','ci-no-data','Sem coordenadas verificadas dos empreendimentos nesta fonte. Nenhuma distância foi estimada.'));wrap.append(note);
}
async function ibge(o){
 const wrap=panels.ibge;wrap.replaceChildren();
 const top=panel('Potencial demográfico — Censo 2022','region','Resultados oficiais em escala municipal; não equivalem automaticamente ao entorno do empreendimento.');
 const cities=rows(o,'Cidade').sort((a,b)=>b.count-a.count);
 const chosen=cities[0]?.label||'';
 top.append(text('p','ci-no-data',chosen?'Município de referência: '+chosen+'. Para análise por raio/setor é necessário georreferenciar o terreno e cruzar a malha de setores do Censo 2022.':'Nenhum município disponível para esta seleção.'));
 const status=text('p','ci-ibge-status','Consultando fontes oficiais disponíveis…');top.append(status);wrap.append(top);
 const foot=text('p','ci-data-note','Fonte: IBGE, Censo Demográfico 2022. Indicadores municipais não representam necessariamente a vizinhança do empreendimento. Dados setoriais e socioeconômicos precisam de processamento geoespacial validado.');
 wrap.append(foot);
 if(!chosen){status.textContent='Sem município associado ao filtro.';return;}
 const session=++ibgeSession;
 try{
  const places=await fetch('https://servicodados.ibge.gov.br/api/v1/localidades/municipios',{signal:AbortSignal.timeout(12000)}).then(r=>{if(!r.ok)throw Error('Municípios indisponíveis');return r.json();});
  if(currentTab!=='ibge'||session!==ibgeSession)return;
  const matches=places.filter(p=>norm(p.nome)===norm(chosen));
  if(matches.length!==1){status.textContent='Município ambíguo ou sem correspondência exata com o IBGE: '+chosen+'.';return;}
  const id=matches[0].id;
  const url='https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/variaveis/93%7C6318%7C614?localidades=N6%5B'+id+'%5D';
  const rows=await fetch(url,{signal:AbortSignal.timeout(12000)}).then(r=>{if(!r.ok)throw Error('Agregados indisponíveis');return r.json();});
  if(currentTab!=='ibge'||session!==ibgeSession)return;
  const values=new Map();
  for(const variable of rows){const v=variable.variavel;const series=variable.resultados?.[0]?.series?.[0]?.serie;const n=Number(series?.['2022']);if(Number.isFinite(n))values.set(v,n);}
  status.replaceChildren();
  const stats=text('div','ci-ibge-stats');
  const patterns=[['População residente',/populacao residente/i,'pessoas'],['Densidade demográfica',/densidade demografica/i,'hab./km²'],['Área territorial',/area territorial/i,'km²']];
  for(const [label,pattern,unit]of patterns){const entry=[...values].find(([key])=>pattern.test(key));stats.append(metric(label,entry?nf(entry[1]):'—','IBGE · 2022 · '+unit,'region'));}
  status.append(stats);
  const a=text('a','ci-source-link','Consultar publicação do Censo 2022 no IBGE');
  a.href='https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html';a.target='_blank';a.rel='noopener noreferrer';top.append(a);
 }catch(error){if(session===ibgeSession)status.textContent='Consulta oficial indisponível no momento. Não foram utilizadas estimativas substitutas.';}
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
 wrap.append(text('p','ci-data-note','Não há conversão de leads comparável nesta fonte. Ticket médio usa a base de vendas, e o perfil usa agregados demográficos de cobertura distinta.'));
}
function attachMap(){
 const map=$('lcmBuyerMap');if(!map)return;
 const target=panels[currentTab==='origin'?'origin':'overview'].querySelector('.ci-map-anchor');
 if(target&&map.parentElement!==target){target.append(map);map.classList.add('ci-owned-map');setTimeout(()=>map.lcmBuyerMap?.invalidateSize(),150);}
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