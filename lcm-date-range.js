/* Cobertura e seleção de datas: usar somente períodos realmente publicados. */
(function(root){
'use strict';
const DAY=86400000;
function validDay(value){
 if(typeof value!=='string'||!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(value))return false;
 const date=new Date(value+'T00:00:00Z');
 return Number.isFinite(date.getTime())&&date.toISOString().slice(0,10)===value;
}
function validPeriod(period){return period&&validDay(period.since)&&validDay(period.until)&&period.since<=period.until}
function intersect(periods,maxDays=90){
 const valid=periods.filter(validPeriod);
 if(!valid.length)return null;
 let since=valid.map(p=>p.since).sort().at(-1),until=valid.map(p=>p.until).sort()[0];
 if(since>until)return null;
 const floor=new Date(new Date(until+'T00:00:00Z').getTime()-(maxDays-1)*DAY).toISOString().slice(0,10);
 if(since<floor)since=floor;
 return {since,until};
}
function select(bounds,previous,choice={}){
 if(!validPeriod(bounds))return null;
 const clamp=value=>value<bounds.since?bounds.since:value>bounds.until?bounds.until:value;
 const followsStart=previous&&choice.since===previous.since;
 const followsEnd=previous&&choice.until===previous.until;
 const since=followsStart||!validDay(choice.since)?bounds.since:clamp(choice.since);
 const until=followsEnd||!validDay(choice.until)?bounds.until:clamp(choice.until);
 return since<=until?{since,until}:{since:bounds.since,until:bounds.until};
}
root.LcmDateRange=Object.freeze({intersect,select,validPeriod});
})(globalThis);

