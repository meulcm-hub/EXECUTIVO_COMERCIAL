const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const code=fs.readFileSync('lcm-leads.js','utf8');
const renderSource=code.slice(code.indexOf('function render(){'),code.indexOf('\nfunction csv(){'));
test('período antes da coorte não oculta gráficos se base integral falhou',()=>{
 const state={source:{period:{since:'2026-01-01',until:'2026-11-14'}},allHistory:null,groups:[]};
 const selected=[],drawn=[],elements={};
 const message={textContent:''};
 const f={since:'2022-01-01',until:'2026-11-14',project:'all',stage:'all',origins:new Set(),visitMedia:new Set()};
 const build=new Function('state','filters','renderAllHistory','selectedOnlyFromFull','$','dateValid','selected','counts','fmt','drawKpis','drawOpportunityFunnels','drawOrigins','drawTrend','drawProjects','insights',renderSource+'; return render;');
 const render=build(state,()=>f,()=>{},()=>false,id=>id==='scopeNote'?message:(elements[id]??={hidden:false}),
  ()=>true,x=>{selected.push(x);return[{stage:0}]},()=>({total:1}),String,
  ()=>drawn.push('kpi'),()=>drawn.push('funil'),()=>{},()=>{},()=>{},()=>{});
 render();
 assert.equal(elements.visao.hidden,false);
 assert.equal(elements.funil.hidden,false);
 assert.deepEqual(drawn,['kpi','funil']);
 assert.equal(selected[0].since,'2026-01-01');
 assert.match(message.textContent,/Visão parcial restaurada/);
});
