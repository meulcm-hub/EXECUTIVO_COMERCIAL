/* Navegação e aparência compartilhadas pelas visões LCM. */
(()=>{
'use strict';
const icons={
home:'<path d="m3 10 9-7 9 7v10H3z"/><path d="M9 20v-7h6v7"/>',
sales:'<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V3h8v4M3 12h18M10 12v3h4v-3"/>',
marketing:'<path d="m3 9 13-5v15L3 14zM16 9h4v5h-4M5 15l2 6h3l-2-5"/>',
funnel:'<path d="M3 4h18l-7 8v7l-4 2v-9z"/>',
audit:'<rect x="5" y="5" width="14" height="16" rx="2"/><path d="M9 5V3h6v2M9 12l2 2 4-4"/>',
people:'<circle cx="9" cy="7" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6M18 14a5 5 0 0 1 3 5"/>',
moon:'<path d="M20 15A9 9 0 0 1 9 4 9 9 0 1 0 20 15z"/>',
sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5"/>',
menu:'<path d="M3 6h18M3 12h18M3 18h18"/>',
money:'<circle cx="12" cy="12" r="9"/><path d="M15 8H10a2 2 0 0 0 0 4h4a2 2 0 0 1 0 4H8M12 6v12"/>'
};
window.LcmIcon=name=>'<svg viewBox="0 0 24 24" aria-hidden="true">'+(icons[name]||icons.home)+'</svg>';
const body=document.body;
// A navegação entre visões também precisa renovar o HTML em cache.
const uiVersion='20261112-colunas';
function pageUrl(href){
 const url=new URL(href,location.href);
 url.searchParams.set('ui',uiVersion);
 return url.pathname+url.search+url.hash;
}
const root=body.dataset.lcmPage==='executive';
const menu=[
['overview','Visão Geral','index.html#overview','home'],
['exec','Executivo Comercial','index.html#exec','sales'],
['marketing','Marketing','marketing.html','marketing'],
['audience','Público Comprador','index.html#audience','people']
];
body.classList.add('lcm-app');
const sidebar=document.createElement('aside');sidebar.className='lcm-sidebar';sidebar.id='lcmSidebar';
sidebar.innerHTML='<button type="button" class="lcm-mobile-close" aria-label="Fechar menu">×</button><a class="lcm-brand" href="'+pageUrl('index.html#overview')+'"><span class="lcm-brand-mark" aria-hidden="true"><i></i><i></i><i></i></span><span><b>LCM</b><small>Inteligência Comercial</small></span></a><div class="lcm-sidebar-label">Seu negócio, em perspectiva</div><nav class="lcm-nav" aria-label="Navegação principal">'+menu.map(([key,label,href,icon])=>'<a data-lcm-view="'+key+'" href="'+pageUrl(href)+'">'+LcmIcon(icon)+'<span>'+label+'</span></a>').join('')+'</nav><div class="lcm-sidebar-bottom"><b>Comercial + Marketing</b>Indicadores para decidir melhor.</div>';
const topbar=document.createElement('div');topbar.className='lcm-topbar';
topbar.innerHTML='<button class="lcm-menu-toggle" type="button" aria-label="Abrir menu" aria-controls="lcmSidebar" aria-expanded="false">'+LcmIcon('menu')+'</button><strong id="lcmBreadcrumb">LCM / Visão Geral</strong><span>Painel de inteligência</span><button id="lcmThemeToggle" class="lcm-theme-toggle" type="button" aria-label="Ativar tema escuro" title="Alternar tema">'+LcmIcon('moon')+'<span>Alternar tema</span></button>';
const scrim=document.createElement('button');scrim.className='lcm-scrim';scrim.hidden=true;scrim.setAttribute('aria-label','Fechar menu');
body.prepend(sidebar,topbar,scrim);
document.querySelectorAll('a.lcm-overview-link[href]').forEach(link=>{
 const href=link.getAttribute('href');
 if(href&&!href.startsWith('#'))link.setAttribute('href',pageUrl(href));
});
const toggle=topbar.querySelector('.lcm-menu-toggle');
function closeMenu(){body.classList.remove('lcm-menu-open');scrim.hidden=true;toggle.setAttribute('aria-expanded','false')}
toggle.addEventListener('click',()=>{const open=body.classList.toggle('lcm-menu-open');scrim.hidden=!open;toggle.setAttribute('aria-expanded',String(open));if(open)sidebar.querySelector('a').focus()});
sidebar.querySelector('.lcm-mobile-close').onclick=()=>{closeMenu();toggle.focus()};
scrim.onclick=closeMenu;
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&body.classList.contains('lcm-menu-open')){closeMenu();toggle.focus()}});
const themeButton=document.getElementById('lcmThemeToggle');
const preference=window.matchMedia('(prefers-color-scheme: dark)');
let manualTheme=null;
try{const saved=localStorage.getItem('lcm-theme');if(saved==='dark'||saved==='light')manualTheme=saved}catch(_){}
function setTheme(theme){
 document.documentElement.dataset.theme=theme;
 const dark=theme==='dark';
 themeButton.innerHTML=LcmIcon(dark?'sun':'moon')+'<span>'+(dark?'Tema claro':'Tema escuro')+'</span>';
 themeButton.setAttribute('aria-label','Ativar tema '+(dark?'claro':'escuro'));
 themeButton.setAttribute('aria-pressed',String(dark));
}
setTheme(manualTheme||(preference.matches?'dark':'light'));
themeButton.onclick=()=>{manualTheme=document.documentElement.dataset.theme==='dark'?'light':'dark';setTheme(manualTheme);try{localStorage.setItem('lcm-theme',manualTheme)}catch(_){}};
preference.addEventListener('change',()=>{if(!manualTheme)setTheme(preference.matches?'dark':'light')});
function active(){
 const hash=location.hash.slice(1);
 const key=root?(['overview','exec','audience'].includes(hash)?hash:'overview'):'marketing';
 if(root){document.querySelector('main>nav button[data-view="'+key+'"]')?.click();document.body.classList.toggle('lcm-show-overview',key==='overview')}
 sidebar.querySelectorAll('a[data-lcm-view]').forEach(link=>{if(link.dataset.lcmView===key)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current')});
 document.getElementById('lcmBreadcrumb').textContent='LCM / '+menu.find(x=>x[0]===key)[1];
 if(root){const head=document.querySelector('.site-header');if(head)head.hidden=key==='overview'}
 closeMenu();
}
sidebar.querySelectorAll('a').forEach(link=>link.addEventListener('click',()=>closeMenu()));
window.addEventListener('hashchange',active);active();
})();

