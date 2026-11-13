/* Público Comprador — reorganização real dos cartões preservando nós e atualizações da fonte. */
(()=>{
'use strict';
const root=document.getElementById('audience');
if(!root||root.dataset.premiumReady==='2')return;
root.dataset.premiumReady='2';
root.classList.add('aud-premium','aud-premium-v2');
const make=(tag,cls,value)=>{
 const n=document.createElement(tag);
 if(cls)n.className=cls;
 if(value!==undefined)n.textContent=value;
 return n;
};
const labels={
 overview:['Visão Geral','◫'],
 profile:['Perfil do Comprador','◎'],
 origin:['Origem Geográfica','⌖'],
 region:['Potencial da Região (IBGE)','▧'],
 compare:['Comparativo por Empreendimento','▥']
};
let heading=root.querySelector('.aud-premium-heading');
if(!heading){
 heading=make('header','aud-premium-heading');
 const text=make('div','aud-premium-heading-text');
 text.append(make('span','aud-premium-eyebrow','INTELIGÊNCIA COMERCIAL · LCM'),make('h1','','Público Comprador'),make('p','','Perfil, origem e comportamento dos compradores'));
 const actions=make('div','aud-premium-actions');
 const exportButton=make('button','aud-premium-export','Exportar PDF');
 exportButton.type='button';
 exportButton.addEventListener('click',()=>window.print());
 actions.append(exportButton);
 heading.append(text,actions);
 root.prepend(heading);
}
let tabs=root.querySelector('.aud-premium-tabs');
if(!tabs){tabs=make('nav','aud-premium-tabs');heading.after(tabs);}
tabs.replaceChildren();
tabs.setAttribute('aria-label','Navegação do Público Comprador');
const stage=make('div','aud-premium-stage');
const views={};
for(const [key,[label,symbol]]of Object.entries(labels)){
 const button=make('button','aud-premium-tab');
 button.type='button';
 button.dataset.premiumTab=key;
 button.append(make('span','aud-premium-tab-icon',symbol),make('span','',label));
 button.addEventListener('click',()=>setTab(key,true));
 tabs.append(button);
 const group=make('section','aud-premium-group aud-premium-group-'+key);
 group.dataset.premiumArea=key;
 group.setAttribute('aria-label',label);
 views[key]=group;
 stage.append(group);
}
const overview=views.overview;
const kpis=root.querySelector('#audienceKpis');
const filter=root.querySelector('.filters');
if(filter){filter.classList.add('aud-premium-filters');filter.after(stage);}
else tabs.after(stage);
if(kpis){kpis.classList.add('aud-premium-kpis');overview.append(kpis);}
const sections={
 demographic:make('div','aud-premium-grid aud-premium-grid-demographic'),
 origin:make('div','aud-premium-grid aud-premium-grid-origin'),
 others:make('div','aud-premium-grid aud-premium-grid-others')
};
const overviewHeader=make('h2','aud-premium-section-title','Perfil dos compradores');
overview.append(overviewHeader,sections.demographic);
const originHeader=make('h2','aud-premium-section-title','Origem dos compradores');
overview.append(originHeader,sections.origin);
const othersHeader=make('h2','aud-premium-section-title','Profissão e outras informações');
overview.append(othersHeader,sections.others);
const messages={
 region:'Indicadores do IBGE ainda não estão disponíveis nessa base. Não exibimos projeções sem fonte validada.',
 compare:'O comparativo por empreendimento depende da seleção de todos os empreendimentos e de métricas equivalentes. Os dados ainda não estão disponíveis nesta visão.'
};
for(const key of ['region','compare']){
 views[key].append(make('p','aud-premium-empty',messages[key]));
}
function kind(panel){
 const heading=panel.querySelector('.aud-panel-title h2,.aud-panel-title,h2,h3');
 const title=(heading?.textContent||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
 if(/sexo|genero|faixa etaria|idade|renda|estado civil/.test(title))return 'demographic';
 if(/cidade|municipio|bairro|origem|localizacao|cep/.test(title))return 'origin';
 return 'others';
}
const moved=new Set();
function relocate(){
 const panels=[...root.querySelectorAll('.aud-panel')];
 for(const panel of panels){
  if(moved.has(panel)||panel.closest('#lcmBuyerMap'))continue;
  const category=kind(panel);
  sections[category].append(panel);
  panel.classList.add('aud-premium-card');
  moved.add(panel);
 }
 const map=document.getElementById('lcmBuyerMap');
 if(map&&!map.dataset.premiumPlaced){
  map.dataset.premiumPlaced='1';map.classList.add('aud-premium-map');
  sections.origin.prepend(map);
  setTimeout(()=>map.lcmBuyerMap?.invalidateSize(),80);
 }
 for(const [heading,container]of [[overviewHeader,sections.demographic],[originHeader,sections.origin],[othersHeader,sections.others]]){
  heading.hidden=!container.children.length;
 }
}
function updateMode(key){
 for(const [name,group]of Object.entries(views)){
  const active=key===name;
  group.hidden=!(key==='overview'?name==='overview':active);
 }
 const all=key==='overview';
 if(!all&&(key==='profile'||key==='origin')){
  // Exibição dedicada dos mesmos gráficos, sem cloná-los ou perder listeners.
  const target=key==='profile'?sections.demographic:sections.origin;
  views[key].append(target);
 }else{
  for(const [container,after]of [[sections.demographic,overviewHeader],[sections.origin,originHeader],[sections.others,othersHeader]]){
   if(container.previousElementSibling!==after)after.after(container);
  }
 }
 if(key==='profile'||key==='origin')views[key].hidden=false;
 const indicators=root.querySelector('#audienceKpis');
 if(indicators)indicators.hidden=!all;
 overviewHeader.hidden=!all||!sections.demographic.children.length;
 originHeader.hidden=!all||!sections.origin.children.length;
 othersHeader.hidden=!all||!sections.others.children.length;
 for(const button of tabs.querySelectorAll('button')){
  const chosen=button.dataset.premiumTab===key;
  button.classList.toggle('is-active',chosen);
  button.setAttribute('aria-current',chosen?'page':'false');
 }
 const map=document.getElementById('lcmBuyerMap');
 if(map&&key!=='origin'&&!all)map.lcmBuyerMap?.invalidateSize();
 if(key==='origin'||all)setTimeout(()=>map?.lcmBuyerMap?.invalidateSize(),100);
}
let active='overview';
function setTab(key,scroll){
 active=key;
 updateMode(key);
 if(scroll)stage.scrollIntoView({behavior:'smooth',block:'start'});
}
relocate();
setTab('overview',false);
// O mapa é carregado sob demanda. Só observar inserções diretas para evitar
// loop de MutationObserver quando os cartões forem reposicionados.
const watch=new MutationObserver(()=>{
 const map=document.getElementById('lcmBuyerMap');
 if(map&&!map.dataset.premiumPlaced){
  watch.disconnect();
  relocate();
  setTab(active,false);
  watch.observe(root,{childList:true,subtree:true});
 }
});
watch.observe(root,{childList:true,subtree:true});
window.addEventListener('hashchange',()=>{if(location.hash==='#audience'){relocate();setTab(active,false);}});
})();