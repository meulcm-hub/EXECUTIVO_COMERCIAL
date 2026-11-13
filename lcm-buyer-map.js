/* Localidades agregadas do Público Comprador. Não utiliza endereços individuais. */
(function(root){
'use strict';
const norm=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim().replace(/\s+/g,' ');
const colors=['#3b9bff','#8b5bd7','#e24b4b','#bd3ee6','#e64ca3','#273be0','#f17739','#22b8a2','#b8a52d','#8ac451','#cf7356','#42bbdc','#d2b4f0'];
function validSource(source){
 if(source?.schema_version!==1||source.coverage?.min_group_size!==5||!Array.isArray(source.cities)||!Array.isArray(source.neighborhoods))return false;
 return [['cities','city'],['neighborhoods','neighborhood']].every(([key,precision])=>source[key].every(p=>p&&typeof p.project==='string'&&p.project&&typeof p.city==='string'&&/^[A-Z]{2}$/.test(p.uf)&&Number.isFinite(p.lat)&&Number.isFinite(p.lng)&&p.lat>=-34&&p.lat<=6&&p.lng>=-74&&p.lng<=-32&&Number.isSafeInteger(p.count)&&p.count>=5&&p.precision===precision&&(key!=='neighborhoods'||typeof p.neighborhood==='string'&&p.neighborhood)));
}
function pointsFor(source,project,mode,city){
 if(!validSource(source))return [];
 const key=norm(project),rows=mode==='neighborhoods'?source.neighborhoods:source.cities;
 return rows.filter(p=>(!key||norm(p.project)===key)&&(!city||norm(p.city)===city.city&&p.uf===city.uf));
}
function groupLocations(points){
 const groups=new Map();
 for(const p of points){
  const key=[norm(p.city),p.uf,norm(p.neighborhood),p.lat,p.lng].join('|');
  if(!groups.has(key))groups.set(key,{city:p.city,uf:p.uf,neighborhood:p.neighborhood||'',lat:p.lat,lng:p.lng,projects:new Map()});
  const group=groups.get(key);group.projects.set(p.project,(group.projects.get(p.project)||0)+p.count);
 }
 return [...groups.values()];
}
const helpers={norm,validSource,pointsFor,groupLocations};
if(typeof document==='undefined'){root.LcmBuyerMap=helpers;if(typeof module!=='undefined')module.exports=helpers;return;}
function node(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=String(text);return e;}
function mount(host,settings){
 if(typeof host==='string')host=document.querySelector(host);if(!host)throw Error('Contêiner do mapa ausente');
 if(host.lcmBuyerMap)return host.lcmBuyerMap;settings=settings||{};
 const L=settings.leaflet||root.L,select=settings.projectSelect||document.getElementById('audienceProject');
 let source=null,map=null,markers=null,tile=null,labels=null,project=select?.value||'',mode='cities',focusCity=null,sequence=0,disposed=false,started=false;
 host.classList.add('panel','lcm-buyer-map');
 const heading=node('div','bm-heading'),title=node('div');title.append(node('h2','','Localização dos compradores'),node('p','','Cidades e bairros com localização confirmada.'));
 const controls=node('div','bm-controls'),modeLabel=node('label','','Localização por'),modeSelect=node('select');
 for(const [value,text]of [['cities','Cidade'],['neighborhoods','Bairro']]){const e=node('option','',text);e.value=value;modeSelect.append(e);}modeLabel.append(modeSelect);
 const layerLabel=node('label','','Visualização'),layerSelect=node('select');for(const [value,text]of [['satellite','Satélite'],['streets','Ruas']]){const e=node('option','',text);e.value=value;layerSelect.append(e);}layerLabel.append(layerSelect);
 const reset=node('button','bm-reset','Ver Brasil');reset.type='button';controls.append(modeLabel,layerLabel,reset);heading.append(title,controls);
 const context=node('p','bm-context'),legend=node('div','bm-legend'),status=node('p','bm-status','Carregando localizações…');status.setAttribute('role','status');
 const canvas=node('div','bm-canvas');canvas.setAttribute('role','region');canvas.setAttribute('aria-label','Mapa interativo de cidades e bairros dos compradores');canvas.tabIndex=0;
 const foot=node('p','bm-footnote','Pontos agregados por localidade. Clique em um ponto para consultar os compradores por empreendimento.');host.replaceChildren(heading,context,legend,status,canvas,foot);
 const names=new Map();for(const option of select?.options||[])if(option.value)names.set(norm(option.value),option.textContent);
 const projectName=value=>names.get(norm(value))||String(value).replace(/\b\w/g,c=>c.toUpperCase());
 let palette=new Map();
 function visible(){const view=host.closest('.view')||host.closest('#audience')||host;return getComputedStyle(view).display!=='none'&&!view.hidden&&host.getBoundingClientRect().width>0;}
 function color(p){return palette.get(p)||colors[0];}
 function pie(group){
  const values=[...group.projects],total=values.reduce((s,[,n])=>s+n,0),size=Math.min(48,24+Math.sqrt(total)*1.2),r=18;let angle=-Math.PI/2;
  let svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" width="'+size+'" height="'+size+'" aria-hidden="true">';
  if(values.length===1)svg+='<circle cx="20" cy="20" r="18" fill="'+color(values[0][0])+'"/>';
  else for(const [p,n]of values){const end=angle+n/total*Math.PI*2;svg+='<path d="M20 20 L'+(20+r*Math.cos(angle))+' '+(20+r*Math.sin(angle))+' A18 18 0 '+(end-angle>Math.PI?1:0)+' 1 '+(20+r*Math.cos(end))+' '+(20+r*Math.sin(end))+' Z" fill="'+color(p)+'"/>';angle=end;}
  return {html:svg+'<circle cx="20" cy="20" r="18" fill="none" stroke="#0e2438" stroke-width="1.5"/></svg>',size};
 }
 function basemap(){
  if(!map)return;if(tile)map.removeLayer(tile);if(labels){map.removeLayer(labels);labels=null;}
  if(layerSelect.value==='streets')tile=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'});
  else tile=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{maxZoom:19,attribution:'Tiles &copy; Esri — Esri, Maxar, Earthstar Geographics, GIS User Community'});
  tile.on('tileerror',()=>{if(!disposed&&map)status.textContent='O fundo do mapa está temporariamente indisponível. Você pode tentar a visualização Ruas.';});tile.addTo(map);
  if(layerSelect.value!=='streets')labels=L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',{maxZoom:19,pane:'overlayPane',opacity:.85}).addTo(map);
 }
 function initialize(){if(map)return true;if(!L?.map){status.textContent='Não foi possível abrir o mapa. Atualize a página para tentar novamente.';return false;}map=L.map(canvas,{scrollWheelZoom:false}).setView([-14.2,-51.9],4);markers=L.layerGroup().addTo(map);basemap();return true;}
 function popup(group){
  const box=node('div','bm-popup');box.append(node('strong','',group.neighborhood?group.neighborhood+' · '+group.city+'/'+group.uf:group.city+'/'+group.uf));
  const list=node('ul');for(const [p,n]of [...group.projects].sort((a,b)=>b[1]-a[1])){const item=node('li'),dot=node('i');dot.style.background=color(p);item.append(dot,node('span','',projectName(p)),node('b','',n.toLocaleString('pt-BR')));list.append(item);}box.append(list);
  if(mode==='cities'&&pointsFor(source,project,'neighborhoods',{city:norm(group.city),uf:group.uf}).length){const button=node('button','bm-popup-button','Ver bairros desta cidade');button.type='button';button.onclick=()=>{focusCity={city:norm(group.city),uf:group.uf};mode=modeSelect.value='neighborhoods';draw(true);};box.append(button);}return box;
 }
 function draw(fit){
  context.textContent=select?.selectedOptions?.[0]?.textContent||'Todos os empreendimentos';if(!source||!visible())return;if(!initialize())return;
  const groups=groupLocations(pointsFor(source,project,mode,focusCity));markers.clearLayers();legend.replaceChildren();
  const projects=[...new Set(groups.flatMap(g=>[...g.projects.keys()]))].sort();for(const p of projects){const item=node('span'),dot=node('i');dot.style.background=color(p);item.append(dot,node('span','',projectName(p)));legend.append(item);}
  for(const g of groups){const icon=pie(g);L.marker([g.lat,g.lng],{icon:L.divIcon({className:'bm-marker',html:icon.html,iconSize:[icon.size,icon.size],iconAnchor:[icon.size/2,icon.size/2]}),title:(g.neighborhood?g.neighborhood+', ':'')+g.city+'/'+g.uf}).bindPopup(popup(g),{maxWidth:360}).addTo(markers);}
  status.textContent=groups.length?groups.length.toLocaleString('pt-BR')+' '+(mode==='cities'?'cidade(s)':'bairro(s)')+' com localização confirmada'+(focusCity?' em '+focusCity.city+'/'+focusCity.uf:'')+'.':'Não há localidades confirmadas com quantidade suficiente para este filtro.';
  map.invalidateSize();if(fit){if(!project&&!focusCity)map.setView([-14.2,-51.9],4);else if(groups.length===1)map.setView([groups[0].lat,groups[0].lng],mode==='cities'?10:13);else if(groups.length)map.fitBounds(groups.map(g=>[g.lat,g.lng]),{padding:[35,35],maxZoom:mode==='cities'?11:14});}
 }
 async function refresh(){
  if(!visible())return;const current=++sequence;started=true;status.textContent='Carregando localizações…';
  const urls=settings.sourceUrl?[settings.sourceUrl]:['https://raw.githubusercontent.com/meulcm-hub/EXECUTIVO_COMERCIAL/main/data/buyer-locations.json','data/buyer-locations.json'];
  let next=null;for(const value of urls){try{const url=new URL(value,document.baseURI);url.searchParams.set('version',String(Date.now()));const response=await fetch(url,{cache:'no-store'});if(!response.ok)continue;const data=await response.json();if(validSource(data)){next=data;break;}}catch(_){}}
  if(disposed||current!==sequence)return;if(!next){status.textContent='Não foi possível carregar as localizações. Tente atualizar a página.';return;}
  source=next;palette=new Map([...new Set([...source.cities,...source.neighborhoods].map(p=>p.project))].sort().map((p,i)=>[p,colors[i%colors.length]]));draw(true);
 }
 function setProject(value){project=value||'';focusCity=null;draw(true);}
 const change=()=>setProject(select?.value||'');select?.addEventListener('change',change);
 modeSelect.onchange=()=>{mode=modeSelect.value;focusCity=null;draw(true);};layerSelect.onchange=basemap;reset.onclick=()=>{focusCity=null;if(map)map.setView([-14.2,-51.9],4);draw(false);};
 const wake=()=>{if(!visible())return;if(!started)refresh();else{map?.invalidateSize();draw(false);}};
 window.addEventListener('hashchange',wake);const view=host.closest('#audience');const watcher=new MutationObserver(wake);if(view)watcher.observe(view,{attributes:true,attributeFilter:['class','style','hidden']});
 const resizer=typeof ResizeObserver==='function'?new ResizeObserver(()=>map?.invalidateSize()):null;resizer?.observe(canvas);
 const controller={setProject,refresh,invalidateSize(){map?.invalidateSize();},destroy(){disposed=true;sequence++;map?.remove();watcher.disconnect();resizer?.disconnect();select?.removeEventListener('change',change);window.removeEventListener('hashchange',wake);host.replaceChildren();delete host.lcmBuyerMap;}};host.lcmBuyerMap=controller;wake();return controller;
}
root.LcmBuyerMap={...helpers,mount};
})(typeof globalThis!=='undefined'?globalThis:window);
