(()=>{
'use strict';
const $=id=>document.getElementById(id);
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=v=>v==null?'—':Number(v).toLocaleString('pt-BR',{maximumFractionDigits:1});
const tabs=[['overview','Visão Geral'],['folders','Análise de Pastas'],['approval','Aprovação'],['sla','SLA e Produtividade'],['docs','Documentação']];
const dims={project:'Empreendimento',correspondent:'Correspondente',agency:'Imobiliária',broker:'Corretor',manager:'Gestor',status:'Situação'};
const labels={key:'Referência da pasta',client:'Cliente',project:'Empreendimento',unit:'Unidade',broker:'Corretor',agency:'Imobiliária',correspondent:'Correspondente',manager:'Gestor',date:'Cadastro',last_move:'Última movimentação',status:'Situação atual',approval:'Aprovação',age_hours:'Horas na situação'};
let data=null,rows=[],view='overview',page=0,query='';
const content=$('pc-content');
const empty=msg=>'<div class="pc-empty">'+esc(msg||'Dados ainda não disponíveis')+'</div>';
const card=(title,body)=>'<article class="pc-card"><h2>'+esc(title)+'</h2>'+body+'</article>';
const kpis=items=>'<div class="pc-kpis">'+items.map(([k,v])=>'<article class="pc-kpi"><span>'+esc(k)+'</span><strong>'+esc(v)+'</strong></article>').join('')+'</div>';
const group=(rs,key)=>Object.entries(rs.reduce((a,r)=>{const k=r[key]||'Não informado';a[k]=(a[k]||0)+1;return a},Object.create(null))).sort((a,b)=>b[1]-a[1]);
const bars=(items,limit=15)=>items.length?items.slice(0,limit).map(([k,v])=>'<div class="pc-row"><span>'+esc(k)+'</span><span class="pc-track"><i style="width:'+Math.max(1,v/Math.max(...items.map(x=>x[1]),1)*100)+'%"></i></span><b>'+fmt(v)+'</b></div>').join(''):empty('Sem registros no período');
const mean=vs=>vs.length?vs.reduce((a,b)=>a+b,0)/vs.length:null;
const approved=r=>['Aprovado integral','Aprovado condicionado','Aprovado em outro CCA','Aprovado'].includes(r.approval);
const analyzed=r=>approved(r)||r.approval==='Reprovado';
const count=fn=>data?rows.filter(fn).length:null;
const ratio=(a,b)=>b?fmt(a/b*100)+'%':'—';
const days=()=>{const a=$('pc-from').value,b=$('pc-to').value;return a&&b?Math.max(1,(Date.parse(b)-Date.parse(a))/864e5+1):null};
function metrics(){
 const total=data?rows.length:null,a=count(analyzed),ap=count(approved),r=count(x=>x.approval==='Reprovado'),pending=count(x=>x.approval?.startsWith('Pendente'));
 const times=rows.filter(x=>Number.isFinite(x.analysis_hours)).map(x=>x.analysis_hours),avg=mean(times);
 return [['Total de Pastas',fmt(total)],['Analisados',fmt(a)],['Não Analisados','—'],['Pendentes',fmt(pending)],['Aprovados',fmt(ap)],['Reprovados',fmt(r)],['Taxa de Aprovação',ratio(ap,a)],['Tempo Médio',avg==null?'—':fmt(avg)+' h'],['Média Diária',days()&&a!=null?fmt(a/days()):'—'],['Média Semanal',days()&&a!=null?fmt(a/days()*7):'—']];
}
function stageTimes(){const groups={};for(const r of rows)for(const e of r.history||[])if(Number.isFinite(e.hours)){(groups[e.stage]??=[]).push(e.hours)}return Object.entries(groups).map(([k,v])=>[k,Math.round(mean(v)*10)/10]);}
function monthly(){const groups={};for(const r of rows){if(!r.date||!analyzed(r))continue;const k=r.date.slice(0,7);const g=groups[k]??={a:0,n:0};g.n++;if(approved(r))g.a++}return Object.entries(groups).sort().map(([k,v])=>[k,Math.round(v.a/v.n*1000)/10]);}
function overview(){
 const a=count(analyzed),ap=count(approved);
 const funnel=data?'<div class="pc-funnel">'+[['Pastas',rows.length,100],['Analisados',a,85],['Aprovados',ap,65]].map(([k,v,w])=>'<div style="width:'+w+'%">'+fmt(v)+' · '+k+'</div>').join('')+'</div>':empty();
 return kpis(metrics())+'<div class="pc-grid">'+card('Funil de Aprovação',funnel)+card('Pipeline Atual do Pré-Cadastro',data?bars(group(rows,'status')):empty())+card('Tempo Médio Histórico das Etapas (h)',stageTimes().length?bars(stageTimes()):empty())+card('Taxa de Aprovação Mensal (%)',data?bars(monthly()):empty())+card('Origem das Pastas',data&&rows.some(r=>r.origin)?bars(group(rows,'origin'),Infinity):empty())+card('SLA de Análise',empty('Meta de SLA ainda não definida'))+['project','agency','broker'].map(k=>card('Desempenho por '+dims[k],data?bars(group(rows.filter(approved),k)):empty())).join('')+'</div>';
}
function table(rs,fields){
 const visible=rs.filter(r=>Object.values(r).filter(v=>typeof v==='string').join(' ').toLowerCase().includes(query.toLowerCase()));
 const max=Math.max(1,Math.ceil(visible.length/25));page=Math.min(page,max-1);
 return '<div class="pc-toolbar"><input id="pc-search" aria-label="Pesquisar pasta" placeholder="Pesquisar pasta" value="'+esc(query)+'"><span>'+fmt(visible.length)+' registros</span></div><div class="pc-table-wrap"><table class="pc-table"><thead><tr>'+fields.map(k=>'<th>'+esc(labels[k]||k)+'</th>').join('')+'<th>Ações</th></tr></thead><tbody>'+visible.slice(page*25,page*25+25).map(r=>'<tr>'+fields.map(k=>'<td>'+esc(k==='key'?r.key.slice(0,12):r[k])+'</td>').join('')+'<td><button data-detail="'+esc(r.key)+'">Detalhes</button></td></tr>').join('')+'</tbody></table></div>'+(!visible.length?empty(data?'Nenhuma pasta encontrada':'Aguardando coleta validada'):'')+'<div class="pc-pagination"><button data-page="-1" '+(!page?'disabled':'')+'>Anterior</button><span>'+ (page+1)+' / '+max+'</span><button data-page="1" '+(page+1>=max?'disabled':'')+'>Próxima</button></div>';
}
function approval(){
 const types=['Aprovado integral','Aprovado condicionado','Aprovado em outro CCA','Reprovado','Pendente','Pendente de documentação','Pendente de restrição','Em processamento'];
 return kpis([['Total de análises',fmt(count(analyzed))],['Aprovados',fmt(count(approved))],...types.map(t=>[t,fmt(count(r=>r.approval===t))]),['Próximas do vencimento','—'],['Vencidas','—']])+'<div class="pc-grid">'+card('Pipeline atual',data?bars(group(rows,'status')):empty())+['project','correspondent','agency','broker'].map(k=>card('Aprovações por '+dims[k],data?bars(group(rows.filter(approved),k)):empty())).join('')+'</div>'+card('Histórico de análises',table(rows.filter(analyzed),['key','client','project','status','approval','date','last_move']));
}
function sla(){return kpis([...metrics().slice(7),['Dentro do SLA','—'],['Fora do SLA','—'],['Sem movimentação',data&&rows.some(r=>r.last_move)?fmt(rows.filter(r=>!r.last_move).length):'—']])+'<div class="pc-grid">'+card('Tempo histórico por etapa (h)',stageTimes().length?bars(stageTimes()):empty())+card('SLA de Análise',empty('Aguardando critério de SLA do relatório'))+['manager','correspondent','agency','broker'].map(k=>card('Produtividade · '+dims[k],data?bars(group(rows.filter(analyzed),k)):empty())).join('')+'</div>';}
function docs(){return kpis(['Cadastrados','Enviados','Aprovados','Reprovados','Aguardando análise','Faltantes'].map(k=>['Documentos '+k.toLowerCase(),'—']))+card('Documentação por pasta', '<p>O acompanhamento apresenta somente metadados documentais autorizados. A fonte de documentos ainda precisa ser validada.</p>'+table(rows,['key','client','project','status','manager']));}
function render(){
 $('pc-tabs').innerHTML=tabs.map(([k,label])=>'<button role="tab" data-tab="'+k+'" aria-selected="'+(view===k)+'">'+esc(label)+'</button>').join('');
 content.innerHTML=view==='overview'?overview():view==='folders'?card('Todas as pastas',table(rows,Object.keys(labels))):view==='approval'?approval():view==='sla'?sla():docs();
}
function filter(){rows=(data?.folders||[]).filter(r=>{const a=$('pc-from').value,b=$('pc-to').value;return (!a||r.date>=a)&&(!b||r.date<=b)&&Object.keys(dims).every(k=>!$('pc-'+k).value||r[k]===$('pc-'+k).value)});page=0;render();}
function detail(key){const r=rows.find(x=>x.key===key);if(!r)return;$('pc-detail-content').innerHTML='<div class="pc-details">'+Object.entries(labels).map(([k,l])=>'<div><small>'+esc(l)+'</small>'+esc(k==='key'?r.key.slice(0,12):r[k])+'</div>').join('')+'</div><h2>Histórico de movimentações</h2>'+((r.history||[]).length?r.history.map(e=>'<div class="pc-history">'+esc(e.date)+' · '+esc(e.stage)+'</div>').join(''):empty('Histórico ainda não disponível'))+'<h2>Documentação</h2>'+empty('Metadados documentais ainda não disponíveis');$('pc-detail').showModal();}
function exportRows(){if(!data)return;const keys=Object.keys(labels);const csv=v=>'"'+String(v??'').replace(/^[=+@-]/,"'$&").replace(/"/g,'""')+'"';const blob=new Blob(['\ufeff'+[keys.map(k=>csv(labels[k])).join(';'),...rows.map(r=>keys.map(k=>csv(k==='key'?r.key.slice(0,12):r[k])).join(';'))].join('\r\n')],{type:'text/csv;charset=utf-8'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='precadastro.csv';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);}
 $('pc-selects').innerHTML=Object.entries(dims).map(([k,l])=>'<label>'+l+'<select id="pc-'+k+'"><option value="">Todos</option></select></label>').join('');
 $('pc-filters').onsubmit=e=>{e.preventDefault();filter()};
 $('pc-filters').onreset=()=>setTimeout(()=>{$('pc-from').value='';$('pc-to').value='';query='';filter()},0);
 $('pc-export').onclick=exportRows;
 $('pc-tabs').onclick=e=>{const k=e.target.dataset.tab;if(k){view=k;page=0;query='';location.hash=k;render()}};
 content.onclick=e=>{if(e.target.dataset.detail)detail(e.target.dataset.detail);if(e.target.dataset.page){page+=Number(e.target.dataset.page);render()}};
 content.oninput=e=>{if(e.target.id==='pc-search'){query=e.target.value;page=0;render();const x=$('pc-search');x?.focus();x?.setSelectionRange(query.length,query.length)}};
 document.querySelector('.pc-close').onclick=()=>$('pc-detail').close();
 const initial=location.hash.slice(1);if(tabs.some(t=>t[0]===initial))view=initial;render();
 fetch('data/precadastro.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json()}).then(d=>{if(d.validated!==true||!Array.isArray(d.folders))throw Error();data=d;for(const k of Object.keys(dims)){const values=[...new Set(d.folders.map(r=>r[k]).filter(Boolean))].sort();$('pc-'+k).innerHTML+='<optgroup label="CV CRM">'+values.map(v=>'<option>'+esc(v)+'</option>').join('')+'</optgroup>'} $('pc-status').textContent='CV CRM · Atualizado em '+new Date(d.generated_at_utc).toLocaleString('pt-BR');filter()}).catch(()=>{$('pc-status').textContent='Aguardando primeira publicação validada do CV CRM.';render()});
})();
