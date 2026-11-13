const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('lcm-creatives.js','utf8');
const context={console};
vm.runInNewContext(source,context);
const lib=context.LcmCreatives;
const account='1183301460107081';
const campaignSource={schema_version:2,action_type:'onsite_conversion.lead_grouped',
  action_report_time:'impression',period:{since:'2026-01-01',until:'2026-11-12'},accounts:[
    {account_id:account,campaigns:[
      {campaign_name:'Captação',status:'ACTIVE',daily:{'2026-11-10':{spend:'100.50',form_leads:12,messages:3}}},
      {campaign_name:'Reconhecimento',status:'ACTIVE',daily:{'2026-11-10':{spend:'50',form_leads:0,messages:2}}},
      {campaign_name:'Antiga',status:'PAUSED',daily:{'2026-11-10':{spend:'40',form_leads:6,messages:4}}}
    ]}
  ]};
test('campanhas ativas somam todas conversas, independente do nome da campanha',()=>{
  const data=lib.activeCampaignTotals(campaignSource,{project:account,since:'2026-11-01',until:'2026-11-12'});
  assert.equal(data.spend,150.5);
  assert.equal(data.form_leads,12);
  assert.equal(data.messages,5);
});
test('sem cobertura completa não inventa resultados',()=>{
  assert.equal(lib.activeCampaignTotals(campaignSource,{project:account,since:'2025-12-31',until:'2026-11-12'}),null);
});
test('conta ausente não é considerada zero',()=>{
  assert.equal(lib.activeCampaignTotals(campaignSource,{project:'999',since:'2026-11-01',until:'2026-11-12'}),null);
});
test('anúncios ativos permanecem um recorte distinto',()=>{
  const ads={schema_version:1,period:{since:'2026-01-01',until:'2026-11-12'},ads:[
    {ad_id:'10001',account_id:account,campaign_id:'20001',status:'ACTIVE',
      daily:[{date:'2026-11-10',impressions:1000,clicks:100,spend:'75',form_leads:8,messages:2}]},
    {ad_id:'10002',account_id:account,campaign_id:'20001',status:'PAUSED',
      daily:[{date:'2026-11-10',impressions:500,clicks:20,spend:'40',form_leads:4,messages:1}]}
  ]};
  const selection=lib.query(ads,{project:account,status:'ACTIVE',since:'2026-11-01',until:'2026-11-12'});
  assert.equal(selection.total.spend,75);
  assert.equal(selection.total.form_leads,8);
  assert.equal(lib.activeCampaignTotals(campaignSource,{project:account,since:'2026-11-01',until:'2026-11-12'}).spend,150.5);
});
