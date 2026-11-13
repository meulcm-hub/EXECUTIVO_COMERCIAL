const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const base='http://127.0.0.1:8765/index.html?smoke=ibge-v7#audience';
 const errors=[];
 try{
  for(const [name,width,height] of [['desktop',1536,980],['mobile',390,844]]){
   const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});
   page.on('pageerror',e=>errors.push(name+': '+e.message));
   // External API/tiles cannot be relied on during CI. Browser must remain functional offline.
   await page.route('https://servicodados.ibge.gov.br/**',r=>r.abort());
   await page.route('https://tile.openstreetmap.org/**',r=>r.abort());
   await page.goto(base,{waitUntil:'domcontentloaded'});
   await page.locator('#audience .ci-tab[data-tab="ibge"]').click();
   await page.locator('#audience .ci-op-toolbar select').first().selectOption('RESIDENCIAL TURQUESA PARQUE');
   await page.locator('#audience .ci-op-kpi').first().waitFor({timeout:15000});
   assert.equal(await page.locator('#audience .ci-op-kpi').count(),5);
   assert.equal(await page.locator('#audience .ci-op-campaign').count(),2);
   assert.match(await page.locator('#audience .ci-op-v7').innerText(),/Meta Ads/);
   assert.match(await page.locator('#audience .ci-op-v7').innerText(),/Google Ads/);
   await page.locator('#audience .ci-op-toolbar select').nth(1).selectOption('3');
   await page.locator('#audience .ci-op-layer input').first().waitFor({timeout:15000});
   assert.equal(await page.locator('#audience .ci-op-layer input').count(),4);
   await page.locator('#audience .ci-op-layer input').first().uncheck();
   await page.locator('#audience .ci-op-layer input').first().check();
   await page.locator('#audience .ci-op-generate').click();
   await page.locator('#ci-op-plan-overlay').waitFor();
   assert.match(await page.locator('#ci-op-plan-overlay').innerText(),/PLANO DE CAMPANHA/);
   assert.equal(await page.locator('#ci-op-plan-overlay button').count(),2);
   await page.locator('#ci-op-plan-overlay button').first().click();
   fs.mkdirSync('artifacts',{recursive:true});
   await page.screenshot({path:'artifacts/ibge-v7-'+name+'.png',fullPage:true});
   await page.locator('#audience .ci-tab[data-tab="profile"]').click();
   assert.equal(await page.locator('#audience').evaluate(el=>el.classList.contains('ci-op-mode')),false);
   assert.equal(await page.locator('#audience .ci-view[data-view="profile"]').isVisible(),true);
   await page.close();
  }
  assert.deepEqual(errors,[]);
  console.log('E2E V7 PASS: 5 KPIs, 4 camadas, filtros, campanhas, plano, outras abas, mobile.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
