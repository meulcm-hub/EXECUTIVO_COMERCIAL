const test=require('node:test');
const assert=require('node:assert/strict');
require('../lcm-creatives.js');
const q=globalThis.LcmCreatives;
const jac='347253318197280',jat='1183301460107081',outside='1349139385694575';
const period={since:'2026-01-01',until:'2026-11-12'};
const day=(date,spend,impressions,clicks)=>({date,spend,impressions,clicks,form_leads:2,messages:1});
const ad=(id,account,extra={})=>({ad_id:id,account_id:account,campaign_id:'55',campaign_name:'Campanha',name:'Criativo',status:'ACTIVE',media_type:'image',daily:[day('2026-01-03','10.50',100,10),day('2026-09-02','20.00',200,5)],...extra});
const source={schema_version:1,period,ads:[ad('1',jac),ad('2',jat,{media_type:'video',daily:[day('2026-09-02','80.00',500,15)]}),ad('3',outside),ad('4',jac,{status:'PAUSED',daily:[day('2026-09-04','5',20,1)]})]};
test('seleção anual usa as mesmas quatro contas da tela e CPC ponderado',()=>{
 const result=q.query(source,{project:'all',status:'ACTIVE',...period});
 assert.equal(result.ads.length,2);
 assert.equal(result.total.spend,110.5);
 assert.equal(result.total.clicks,30);
 assert.equal(result.total.cpc,110.5/30);
 assert.equal(result.total.impressions,800);
 assert.equal(result.total.reach,undefined);
});
test('subperíodo filtra dias e não exibe anúncios sem entrega fora do recorte',()=>{
 const result=q.query(source,{project:jac,status:'all',since:'2026-01-01',until:'2026-01-31'});
 assert.equal(result.ads.length,1);
 assert.equal(result.total.spend,10.5);
 assert.equal(result.total.clicks,10);
 const september=q.query(source,{project:jac,status:'PAUSED',since:'2026-09-01',until:'2026-09-30'});
 assert.equal(september.ads.length,1);assert.equal(september.total.spend,5);
});
test('campanha, mídia, status e contas explícitas limitam os mesmos anúncios',()=>{
 const result=q.query(source,{project:'all',media:'video',campaign:jat+'/55',status:'ACTIVE',...period});
 assert.deepEqual(result.ads.map(ad=>ad.ad_id),['2']);
 assert.equal(q.query(source,{accountIds:[outside],...period}).total.spend,30.5);
 assert.equal(q.query(source,{project:jac,media:'video',...period}).ads.length,0);
});
test('anúncios atuais sem entrega podem aparecer com zero e CPC indefinido',()=>{
 const result=q.query({...source,ads:[ad('5',jac,{daily:[]})]},{project:jac,...period});
 assert.equal(result.ads.length,1);assert.equal(result.total.spend,0);assert.equal(result.total.cpc,null);
});
test('agrupamento de campanha preserva contas e calcula CPC por soma',()=>{
 const result=q.query(source,{status:'all',...period});
 const campaigns=q.campaignRows(result.ads);
 assert.equal(campaigns.length,2);
 const jacaranda=campaigns.find(row=>row.ads===2);
 assert.equal(jacaranda.spend,35.5);assert.equal(jacaranda.cpc,35.5/16);
});
test('duplicação e métricas negativas invalidam coleta para evitar dupla contagem',()=>{
 assert.equal(q.validSource({...source,ads:[source.ads[0],source.ads[0]]}),false);
 assert.equal(q.validSource({...source,ads:[ad('1',jac,{daily:[day('2026-01-03',-1,1,1)]})]}),false);
 const duplicate=day('2026-01-03',1,1,1);
 assert.equal(q.validSource({...source,ads:[ad('1',jac,{daily:[duplicate,duplicate]})]}),false);
 assert.equal(q.validSource({...source,ads:[ad('1',jac,{daily:[day('2025-01-01',1,1,1)]})]}),false);
});
test('cobertura é identificada sem inventar indicadores para período desconhecido',()=>{
 assert.equal(q.query(source,{since:'2025-01-01',until:'2025-12-31'}).overlap,false);
 assert.equal(q.query(source,{since:'2025-01-01',until:'2026-01-31'}).partial,true);
 assert.equal(q.query(source,{since:'2026-09-01',until:'2026-01-01'}),null);
});
test('URLs de mídia rejeitam credenciais, javascript e domínios externos',()=>{
 assert.equal(q.safeUrl('https://scontent.example.fbcdn.net/a.jpg?oh=abc',true),'https://scontent.example.fbcdn.net/a.jpg?oh=abc');
 assert.equal(q.safeUrl('https://www.facebook.com/watch/?v=123',false),'https://www.facebook.com/watch/?v=123');
 for(const url of ['javascript:alert(1)','https://evil.example/a.jpg','https://fbcdn.net.evil.example/a','http://fbcdn.net/a','https://user:password@fbcdn.net/a','https://fbcdn.net/a?access_token=secret','https://fbcdn.net/a?TOKEN=secret','https://fbcdn.net:8080/a',' https://fbcdn.net/a','https://fbcdn.net/a?fb_access_token=secret'])assert.equal(q.safeUrl(url,true),'');
 assert.equal(q.safeUrl('https://scontent.fbcdn.net/a',false),'');
});
