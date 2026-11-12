/* A data exibida vem da coleta publicada; abrir ou filtrar a página não a altera. */
(function(root){
  'use strict';
  function formatTimestamp(value){
    if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value))return null;
    const date=new Date(value);
    if(!Number.isFinite(date.getTime()))return null;
    const parts=Object.fromEntries(new Intl.DateTimeFormat('pt-BR',{
      timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit',year:'numeric',
      hour:'2-digit',minute:'2-digit',hourCycle:'h23'
    }).formatToParts(date).map(part=>[part.type,part.value]));
    return parts.day+'/'+parts.month+'/'+parts.year+' '+parts.hour+':'+parts.minute;
  }
  function createTracker(){
    let last=null;
    return {update(value,failed=false){
      const text=formatTimestamp(value);
      // Uma falha de recarga não substitui a coleta diária já carregada por
      // uma data artificial nem por um consolidado anterior.
      if(text&&(!failed||!last))last={datetime:value,text};
      return {datetime:last?.datetime||'',text:last?.text||'Indisponível',
        stale:Boolean(failed&&last)};
    }};
  }
  root.LcmUpdateStatus={formatTimestamp,createTracker};
  if(typeof module!=='undefined'&&module.exports)module.exports=root.LcmUpdateStatus;
})(typeof globalThis!=='undefined'?globalThis:window);
