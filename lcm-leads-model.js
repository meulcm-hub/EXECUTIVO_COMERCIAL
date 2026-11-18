/* Regras de apresentação: situação atual da safra, nunca histórico inferido. */
(function(root){
'use strict';
const norm=x=>String(x??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').trim().toUpperCase();
const stages=['Novo Lead','Em Atendimento','Agendamento','Visita','Análise de Crédito','Venda'];
function stage(raw){const s=norm(raw);
 if(['NOVO LEAD','PROSPECCAO'].includes(s))return 'Novo Lead';
 if(s==='CONTATO'||/^CAD\/C\s*[1-7]$/.test(s)||s==='EM ATENDIMENTO')return 'Em Atendimento';
 if(s==='AGENDAMENTO'||/^CAD\/A\s*(?:[1-9]|1[0-9]|20)$/.test(s))return 'Agendamento';
 if(s==='VISITA')return 'Visita';
 if(s==='ANALISE DE CREDITO')return 'Análise de Crédito';
 if(s==='VENDA REALIZADA')return 'Venda';
 if(['PERDIDO','DESCARTADO','CANCELADO'].includes(s))return 'Perdido';
 return null;
}
function channel(r){const o=norm(r.origin_name||r.origin),m=norm((r.lead_medias||[r.lead_media]).join(' '));if(['FB','FACEBOOK','BC','BUSCA COMPARTILHADA','IG','INSTAGRAM'].includes(o)||/WHATSAPP FACEBOOK/.test(m))return 'Meta Ads';if(['GO','GOOGLE'].includes(o))return 'Google Ads';if(['SI','WEBSITE','SITE','IT','INSTAPAGE','BO','BUSCA ORGANICA'].includes(o))return 'Site / Landing Page';if(['RF','REFERENCIA','INDICACAO'].includes(o))return 'Indicação';return 'Outros';}
const originNames={FB:'Facebook',GO:'Google',GE:'Painel Gestor',BC:'Busca Compartilhada',SI:'WebSite',RF:'Referência',LI:'Ligação',WA:'Whatsapp',IG:'Instagram',ND:'Não definida',CO:'Painel Corretor',BO:'Busca Orgânica',IM:'Painel Imobiliária',OP:'Outras publicidades',MP:'Mídia Paga',PO:'Portais',TD:'Tráfego Direto'};
const origin=r=>r.origin_name||originNames[r.origin]||r.origin||'Não informada';
const date=x=>String(x||'').slice(0,10);
const validDate=x=>/^\d{4}-\d{2}-\d{2}$/.test(x)&&!Number.isNaN(Date.parse(x+'T12:00:00Z'));
function previous(f){if(!validDate(f.since)||!validDate(f.until)||f.since>f.until)return null;const end=new Date(f.since+'T12:00:00Z'),span=Math.round((Date.parse(f.until)-Date.parse(f.since))/86400000)+1;end.setUTCDate(end.getUTCDate()-1);const start=new Date(end);start.setUTCDate(start.getUTCDate()-span+1);return {...f,since:start.toISOString().slice(0,10),until:end.toISOString().slice(0,10)};}
function filter(rows,f){return rows.filter(r=>date(r.date)>=f.since&&date(r.date)<=f.until&&(!f.project||norm(r.project)===norm(f.project))&&(!f.origin||origin(r)===f.origin)&&(!f.status||r.status===f.status)&&(!f.owner||r.owner===f.owner));}
const total=rows=>rows.reduce((n,r)=>n+Number(r.count||0),0);
function metrics(rows){const n=total(rows),known=rows.filter(r=>stage(r.status)),active=total(known.filter(r=>!['Venda','Perdido'].includes(stage(r.status)))),opportunities=total(rows.filter(r=>['Agendamento','Visita','Análise de Crédito'].includes(stage(r.status)))),sales=total(rows.filter(r=>stage(r.status)==='Venda'));return {captured:n,active,opportunities,sales,conversion:n?sales/n*100:0,unclassified:n-total(known)};}
function group(rows,key){const m=new Map();rows.forEach(r=>{const k=typeof key==='function'?key(r):r[key]||'Não informado';m.set(k,(m.get(k)||0)+Number(r.count||0));});return [...m].map(([label,value])=>({label,value})).sort((a,b)=>b.value-a.value);}
function delta(value,before){if(before===0)return value===0?{value:0,text:'0%'}:{value:null,text:'Sem base anterior'};const v=(value-before)/before*100;return {value:v,text:(v>0?'+':'')+new Intl.NumberFormat('pt-BR',{maximumFractionDigits:1}).format(v)+'%'};}
function shortName(s){return String(s||'').trim().split(/\s+/).slice(0,2).join(' ')||'Nome não disponível';}
function csv(rows){return '\ufeff'+rows.map(r=>r.map(v=>'"'+String(v??'').replace(/^[=+@\-\t\r]/,"'$&").replaceAll('"','""')+'"').join(';')).join('\r\n');}
const api={norm,stage,stages,channel,origin,previous,filter,total,metrics,group,delta,shortName,csv,validDate};root.LcmLeadsModel=Object.freeze(api);if(typeof module!=='undefined')module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:window);
