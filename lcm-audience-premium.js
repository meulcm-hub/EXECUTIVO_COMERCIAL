/* Camada de apresentação do Público Comprador. Não altera consultas nem métricas. */
(()=>{
'use strict';
const root=document.getElementById('audience');
if(!root||root.dataset.premiumReady==='1')return;
root.dataset.premiumReady='1';
root.classList.add('aud-premium');
const el=(tag,cls,txt)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(txt!==undefined)node.textContent=txt;return node;};
const icon=(name)=>({users:'♧',profile:'◎',map:'⌖',region:'▧',compare:'▥'}[name]||'•');
const heading=el('div','aud-premium-heading');
const headingText=el('div','aud-premium-heading-text');
const eyebrow=el('span','aud-premium-eyebrow','INTELIGÊNCIA COMERCIAL · LCM');
const h1=el('h1','', 'Público Comprador');
const subtitle=el('p','','Perfil, origem e comportamento dos compradores');
headingText.append(eyebrow,h1,subtitle);
const actions=el('div','aud-premium-actions');
const print=el('button','aud-premium-export','Exportar PDF');
print.type='button';print.title='Imprimir ou salvar este painel em PDF';
print.addEventListener('click',()=>window.print());
actions.append(print);
heading.append(headingText,actions);
const tabs=el('nav','aud-premium-tabs');
tabs.setAttribute('aria-label','Seções do Público Comprador');
const tabItems=[
 ['overview','Visão Geral','users',null],
 ['profile','Perfil do Comprador','profile',/perfil|gênero|genero|sexo|faixa etária|faixa etaria|idade|renda|estado civil|profiss/i],
 ['origin','Origem Geográfica','map',/origem|município|municipio|bairro|cidade|localiza|mapa|cep/i],
 ['region','Potencial da Região (IBGE)','region',/ibge|potencial|região|regiao|popula|renda per capita/i],
 ['compare','Comparativo por Empreendimento','compare',/comparativo|comparação|comparacao|empreendimentos/i]
];
const buttons=new Map();
for(const [key,label,glyph]of tabItems){
 const button=el('button','aud-premium-tab');
 button.type='button';button.dataset.premiumTab=key;
 button.append(el('span','aud-premium-tab-icon',icon(glyph)),el('span','',label));
 button.addEventListener('click',()=>selectTab(key,true));
 tabs.append(button);buttons.set(key,button);
}
const intro=root.querySelector('.heading, .aud-heading, .audience-heading');
if(intro)intro.classList.add('aud-premium-original-heading');
root.prepend(tabs);root.prepend(heading);
const filters=root.querySelector('.filters');
if(filters)filters.classList.add('aud-premium-filters');
const kpis=root.querySelector('#audienceKpis');
if(kpis)kpis.classList.add('aud-premium-kpis');
const locationRoot=()=>document.getElementById('lcmBuyerMap');
function targets(){
 const candidates=[...root.querySelectorAll('.aud-panel, .panel, .aud-section, .aud-block, section')].filter(n=>n!==root&&n!==locationRoot()&&!n.closest('.aud-premium-heading,.aud-premium-tabs,.aud-premium-filters'));
 return candidates.filter(n=>!candidates.some(parent=>parent!==n&&parent.contains(n)));
}
function jump(key){
 if(key==='origin'){const target=locationRoot()||[...root.querySelectorAll('h2,h3')].find(n=>/origem|localiza|mapa/i.test(n.textContent));if(target){target.scrollIntoView({behavior:'smooth',block:'start'});return true;}}
 if(key==='overview'){(kpis||root).scrollIntoView({behavior:'smooth',block:'start'});return true;}
 const match=tabItems.find(x=>x[0]===key)?.[3];
 const found=[...root.querySelectorAll('h2,h3,.aud-panel-title')].find(n=>match?.test(n.textContent||''));
 if(found){found.scrollIntoView({behavior:'smooth',block:'start'});return true;}
 return false;
}
let active='overview';
function selectTab(key,scroll){
 active=key;
 for(const [name,button]of buttons){
  const selected=name===key;
  button.classList.toggle('is-active',selected);
  button.setAttribute('aria-current',selected?'page':'false');
 }
 // As abas são atalhos funcionais. Dados e gráficos continuam montados,
 // garantindo filtros, cálculos, mapas e atualizações sem alterações.
 if(scroll&&!jump(key)){
  const notice=document.getElementById('audPremiumNotice')||el('p','aud-premium-notice');
  notice.id='audPremiumNotice';
  notice.textContent=key==='region'?'Indicadores IBGE ainda não estão disponíveis nesta base. Nenhuma estimativa foi criada.':'Esta seção ainda não tem dados específicos publicados para o filtro selecionado.';
  tabs.after(notice);notice.hidden=false;
 }else{
  const notice=document.getElementById('audPremiumNotice');if(notice)notice.hidden=true;
 }
}
selectTab('overview',false);
const observer=new MutationObserver(()=>{
 const map=locationRoot();if(map)map.classList.add('aud-premium-map');
});
observer.observe(root,{subtree:false,childList:true});
window.addEventListener('hashchange',()=>{if(location.hash==='#audience')selectTab(active,false)});
})();