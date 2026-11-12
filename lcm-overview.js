/* Visão geral: somente agregados, sem duplicar os registros individuais. */
(async()=>{
'use strict';
const $=id=>document.getElementById(id);
if(!$('overview'))return;
const projects=[
{key:'residencial flores do cerrado jacaranda',name:'Jacarandá',account:'347253318197280'},
{key:'residencial village lagoas',name:'Village Lagoas',account:'626593228944023'},
{key:'spe arraial costa verde club',name:'Arraial Costa Verde',account:'332967835423799'},
{key:'residencial jatoba',name:'Jatobá',account:'1183301460107081'}
];
const fmt=n=>n===null?'Em validação':Number(n).toLocaleString('pt-BR');
const brl=n=>n===null?'Indisponível':Number(n).toLocaleString('pt-BR',{style:'currency',currency:'BRL',minimumFractionDigits:2,maximumFractionDigits:2});
const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const days=(a,b)=>{const result=[];for(let d=new Date(a+'T00:00:00Z');d<=new Date(b+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+1))result.push(d.toISOString().slice(0,10));return result};
document.querySelectorAll('[data-icon]').forEach(node=>node.innerHTML=LcmIcon(node.dataset.icon));
projects.forEach(p=>$('ovProject').add(new Option(p.name,p.key)));
const paths=['marketing-daily','cv-funnel','marketing-conversions','marketing-campaigns'];
const loaded=await Promise.allSettled(paths.map(async name=>{
 const r=await fetch('data/'+name+'.json?v='+Date.now(),{cache:'no-store'});
 if(!r.ok)throw Error(name);return r.json();
}));
const [daily,funnel,conversions,campaigns]=loaded.map(r=>r.status==='fulfilled'?r.value:null);
if(!daily?.period?.since||!daily?.period?.until){$('ovStatus').textContent='Histórico indisponível. As visões Executivo e Marketing continuam disponíveis pelo menu.';$('ovSync').textContent='Histórico indisponível';return}
let start=daily.period.since,end=daily.period.until;
for(const source of [funnel,conversions])if(source?.validated===true&&source.period){start=[start,source.period.since].sort().at(-1);end=[end,source.period.until].sort()[0]}
if(start>end){$('ovStatus').textContent='As fontes ainda não têm um período em comum. Aguarde a próxima sincronização.';return}
const dates=days(start,end);const defaultSince=dates[Math.max(0,dates.length-30)];
for(const id of ['ovSince','ovUntil']){$(id).min=start;$(id).max=end}
$('ovSince').value=defaultSince;$('ovUntil').value=end;
function spendFor(p,since,until){
 if(!campaigns?.period||since<campaigns.period.since||until>campaigns.period.until)return null;
 const account=campaigns.accounts?.find(a=>String(a.account_id)===p.account);
 if(!Array.isArray(account?.campaigns))return null;
 return account.campaigns.filter(c=>c.status==='ACTIVE').reduce((sum,c)=>sum+Object.entries(c.daily||{}).filter(([d])=>d>=since&&d<=until).reduce((a,[,v])=>a+(Number(v.spend)||0),0),0);
}
function cohortFor(p,since,until){
 const c=LcmCvQuery.funnelRow(funnel,p.key,since,until);
 const keys=['prospect','agendamento','visita','analise_credito','venda_realizada'];
 return funnel?.validated===true&&LcmCvQuery.validFunnel(funnel)&&c?.validated===true&&keys.every(k=>Number.isInteger(c.counts?.[k])&&c.counts[k]>=0)?c.counts:null;
}
function chart(selected,since,until){
 if(conversions?.validated!==true||!conversions.period||since<conversions.period.since||until>conversions.period.until||
 selected.some(p=>!conversions.daily?.[p.key])){$('ovChart').innerHTML='<div class="empty">Captação diária em validação neste período.</div>';return}
 const sequence=days(since,until).map(date=>({date,facebook:selected.reduce((s,p)=>s+(Number(conversions.daily[p.key][date]?.facebook_new)||0),0),google:selected.reduce((s,p)=>s+(Number(conversions.daily[p.key][date]?.google_new)||0),0)}));
 const W=660,H=240,L=35,R=14,T=15,B=30,max=Math.max(1,...sequence.flatMap(v=>[v.facebook,v.google]));
 const x=i=>L+(W-L-R)*i/Math.max(1,sequence.length-1),y=v=>H-B-v/max*(H-T-B);
 let svg='<svg class="lcm-line-chart" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Novos cadastros diários por origem Facebook e Google">';
 for(let i=0;i<=4;i++){const n=max*i/4;svg+='<line x1="'+L+'" y1="'+y(n)+'" x2="'+(W-R)+'" y2="'+y(n)+'" stroke="currentColor" opacity=".08"/><text x="'+(L-7)+'" y="'+(y(n)+4)+'" text-anchor="end">'+Math.round(n)+'</text>'}
 const labels=[...new Set([0,Math.floor((sequence.length-1)/3),Math.floor(2*(sequence.length-1)/3),sequence.length-1])];
 for(const i of labels)svg+='<text x="'+x(i)+'" y="'+(H-8)+'" text-anchor="middle">'+sequence[i].date.slice(8,10)+'/'+sequence[i].date.slice(5,7)+'</text>';
 for(const [key,color]of [['facebook','#67ae42'],['google','#5793a9']]){
 svg+='<polyline fill="none" stroke="'+color+'" stroke-width="2.7" stroke-linejoin="round" points="'+sequence.map((v,i)=>x(i)+','+y(v[key])).join(' ')+'"/>';
 sequence.forEach((v,i)=>{svg+='<circle cx="'+x(i)+'" cy="'+y(v[key])+'" r="2.6" fill="'+color+'"><title>'+v.date+' · '+key+': '+v[key]+'</title></circle>'});
 }
 $('ovChart').innerHTML=svg+'</svg>';
}
function render(){
 const since=$('ovSince').value,until=$('ovUntil').value;
 if(!since||!until||since>until||since<start||until>end){$('ovStatus').textContent='Escolha um período válido entre '+start+' e '+end+'.';return}
 const selected=projects.filter(p=>$('ovProject').value==='all'||p.key===$('ovProject').value);
 const rows=selected.map(p=>{
 const sales=SALES.filter(s=>norm(s.project)===p.key&&s.date>=since&&s.date<=until);
 return {p,count:sales.length,vgv:sales.reduce((sum,s)=>sum+(Number(s.total)||0),0),cohort:cohortFor(p,since,until),spend:spendFor(p,since,until)};
 });
 const valid=rows.every(r=>r.cohort!==null),spend=rows.every(r=>r.spend!==null)?rows.reduce((s,r)=>s+r.spend,0):null;
 const totals=valid?Object.fromEntries(['prospect','agendamento','visita','analise_credito','venda_realizada'].map(k=>[k,rows.reduce((s,r)=>s+r.cohort[k],0)])):null;
 const verifiedSales=valid&&funnel.sales_link_validated===true;
 $('ovSpend').textContent=brl(spend);$('ovProspects').textContent=fmt(totals?.prospect??null);
 $('ovSales').textContent=fmt(rows.reduce((s,r)=>s+r.count,0));$('ovVgv').textContent=brl(rows.reduce((s,r)=>s+r.vgv,0));
 $('ovCpp').textContent=spend!==null&&totals?.prospect>0?brl(spend/totals.prospect):'—';
 $('ovConversion').textContent=verifiedSales&&totals.prospect>0?(totals.venda_realizada/totals.prospect*100).toLocaleString('pt-BR',{maximumFractionDigits:1})+'%':'Em validação';
 $('ovCohortSales').textContent=fmt(verifiedSales?totals.venda_realizada:null);
 $('ovFunnel').innerHTML=totals?[['prospect','Prospect'],['agendamento','Agendamento'],['visita','Visita'],['analise_credito','Análise de crédito'],['venda_realizada','Venda']].map(([key,label])=>'<div class="lcm-funnel-row"><span>'+label+'</span><div class="lcm-funnel-track"><i style="width:'+(key==='venda_realizada'&&!verifiedSales?0:totals[key]/Math.max(1,totals.prospect)*100)+'%"></i></div><strong>'+(key==='venda_realizada'&&!verifiedSales?'—':fmt(totals[key]))+'</strong></div>').join(''):'<div class="empty">Funil em validação para este período.</div>';
 $('ovProjects').innerHTML=rows.map(r=>'<tr><td>'+escape(r.p.name)+'</td><td>'+fmt(r.cohort?.prospect??null)+'</td><td>'+fmt(r.count)+'</td><td>'+brl(r.vgv)+'</td></tr>').join('');
 $('ovStatus').textContent='Período aplicado: '+since.split('-').reverse().join('/')+' a '+until.split('-').reverse().join('/')+' · '+(selected.length===1?selected[0].name:'4 empreendimentos vinculados')+'.';
 $('ovSync').textContent='Histórico até '+until.split('-').reverse().join('/');
 const stamp=daily.generated_at_utc?new Date(daily.generated_at_utc).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'}):'não informada';
 $('ovSources').textContent='Comercial: base incorporada do relatório executivo, filtrada pela data de venda. Marketing: coleta publicada em '+stamp+'. CV CRM: safra de entrada com evolução até '+(funnel?.as_of||'data não disponível')+'. Os recortes têm regras próprias e não devem ser somados.';
 chart(selected,since,until);
}
$('ovFilters').addEventListener('submit',event=>{event.preventDefault();render()});
$('ovProject').addEventListener('change',render);render();
})();

