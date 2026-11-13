/* Consulta por período sem matriz de todas as combinações de datas. */
(function(root){
'use strict';
const keys=['prospect','agendamento','visita','analise_credito','venda_realizada'];
const covered=(source,since,until)=>source?.validated===true&&source.period&&since>=source.period.since&&until<=source.period.until&&since<=until;
function validFunnel(source){
 if(source?.validated!==true||source.cohort_mode!=='prospect_date')return false;
 if(source.schema_version===1)return Array.isArray(source.cohorts)&&source.cohorts.length>0;
 return source.schema_version===2&&Array.isArray(source.prospects)&&source.prospects.every(group=>typeof group.project==='string'&&Array.isArray(group.entries)&&group.entries.every(entry=>typeof entry.date==='string'&&Number.isInteger(entry.stage)&&entry.stage>=0&&entry.stage<=4));
}
function funnelRow(source,project,since,until){
 if(!covered(source,since,until)||!validFunnel(source))return null;
 if(source.schema_version===1)return source.cohorts.find(row=>row.project===project&&row.since===since&&row.until===until&&row.validated===true)||null;
 const counts=Object.fromEntries(keys.map(key=>[key,0]));
 for(const group of source.prospects){
  if(group.project!==project)continue;
  let first=null;
  for(const entry of group.entries)if(entry.date>=since&&entry.date<=until&&(!first||entry.date<first.date))first=entry;
  if(first)keys.forEach((key,index)=>{if(first.stage>=index)counts[key]++});
 }
 return {project,since,until,as_of:source.as_of,validated:true,counts};
}
function validDate(value){
 if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))return false;
 const date=new Date(value+'T00:00:00Z');
 return Number.isFinite(date.getTime())&&date.toISOString().slice(0,10)===value;
}
function entries(source,projects,since,until){
 if(source?.schema_version!==2||source.classification_version!==1||
    !covered(source,since,until)||!validFunnel(source)||
    !validDate(source.period.since)||!validDate(source.period.until)||
    !validDate(since)||!validDate(until)||!Array.isArray(projects)||!projects.length||
    projects.some(project=>typeof project!=='string'||!project))return null;
 const selected=[...new Set(projects)];
 const blank=()=>({new:0,returning:0,prospect:0,whatsapp_new:0,whatsapp_returning:0});
 const result={totals:blank(),projects:Object.fromEntries(selected.map(project=>[project,blank()])),
   daily:Object.fromEntries(selected.map(project=>[project,{}]))};
 for(const group of source.prospects){
   if(!Object.prototype.hasOwnProperty.call(group,'new_date')||
      typeof group.whatsapp_acquisition!=='boolean'||!group.entries.length||
      group.entries.some(entry=>!validDate(entry.date)||entry.date<source.period.since||entry.date>source.period.until)||
      new Set(group.entries.map(entry=>entry.date)).size!==group.entries.length||
      (group.new_date!==null&&(!validDate(group.new_date)||
        !group.entries.some(entry=>entry.date===group.new_date)||
        group.entries.some(entry=>entry.date<group.new_date))))return null;
   const counts=Object.prototype.hasOwnProperty.call(result.projects,group.project)?result.projects[group.project]:null;
   if(!counts||!group.entries.some(entry=>entry.date>=since&&entry.date<=until))continue;
   counts.prospect++;
   const isNew=group.new_date!==null&&group.new_date>=since&&group.new_date<=until;
   counts[isNew?'new':'returning']++;
   if(group.whatsapp_acquisition)counts[isNew?'whatsapp_new':'whatsapp_returning']++;
   if(isNew){
     const day=result.daily[group.project][group.new_date]||{new:0,whatsapp_new:0};
     day.new++;if(group.whatsapp_acquisition)day.whatsapp_new++;
     result.daily[group.project][group.new_date]=day;
   }
 }
 for(const counts of Object.values(result.projects))for(const key of Object.keys(result.totals))result.totals[key]+=counts[key];
 return result;
}
function conversions(source,since,until){
 if(!covered(source,since,until))return null;
 if(source.schema_version<4)return source.range_unique?.[since+'|'+until]||null;
 if(!Array.isArray(source.unique_groups)||!Array.isArray(source.projects))return null;
 const metrics=['unique','returning','returning_whatsapp','unclassified_return'];
 const result=Object.fromEntries(metrics.map(key=>[key,Object.fromEntries([...source.projects,'all'].map(p=>[p,0]))]));
 for(const group of source.unique_groups){
  const matches={unique:new Set(),returning:new Set(),returning_whatsapp:new Set(),unclassified_return:new Set()};
  for(const event of group.events||[]){
   if(event.date<since||event.date>until||!source.projects.includes(event.project))continue;
   matches.unique.add(event.project);
   if(event.returning)matches.returning.add(event.project);
   if(event.whatsapp)matches.returning_whatsapp.add(event.project);
   if(event.unclassified)matches.unclassified_return.add(event.project);
  }
  for(const key of metrics){for(const p of matches[key])result[key][p]++;if(matches[key].size)result[key].all++;}
 }
 return result;
}
function auditDate(row,since,until){
 const dates=Array.isArray(row.entry_dates)?row.entry_dates:[row.data_entrada];
 return dates.filter(day=>day>=since&&day<=until).sort()[0]||null;
}
root.LcmCvQuery=Object.freeze({validFunnel,funnelRow,entries,conversions,auditDate});
})(globalThis);

