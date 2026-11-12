const test=require('node:test');
const assert=require('node:assert/strict');
require('../lcm-date-range.js');
const range=globalThis.LcmDateRange;
test('interseção real evita dia anterior ao início do CV',()=>{
 assert.deepEqual(range.intersect([{since:'2026-08-14',until:'2026-11-11'},{since:'2026-08-15',until:'2026-11-12'}]),{since:'2026-08-15',until:'2026-11-11'});
});
test('janela completa acompanha avanço diário das fontes',()=>{
 const previous={since:'2026-08-15',until:'2026-11-12'};
 const next={since:'2026-08-16',until:'2026-11-13'};
 assert.deepEqual(range.select(next,previous,previous),next);
});
test('seleção manual válida é preservada',()=>{
 assert.deepEqual(range.select({since:'2026-08-16',until:'2026-11-13'},{since:'2026-08-15',until:'2026-11-12'},{since:'2026-09-01',until:'2026-10-01'}),{since:'2026-09-01',until:'2026-10-01'});
});
test('seleção antiga é limitada ao novo histórico',()=>{
 assert.deepEqual(range.select({since:'2026-08-16',until:'2026-11-13'},null,{since:'2026-08-14',until:'2026-11-11'}),{since:'2026-08-16',until:'2026-11-11'});
});
test('fontes sem interseção não criam um período nem zeros',()=>{
 assert.equal(range.intersect([{since:'2026-08-01',until:'2026-08-31'},{since:'2026-09-01',until:'2026-09-30'}]),null);
 assert.equal(range.select(null,null,{}),null);
});
test('fonte opcional ausente não bloqueia fonte disponível',()=>{
 assert.deepEqual(range.intersect([null,undefined,{since:'2026-10-01',until:'2026-10-31'}]),{since:'2026-10-01',until:'2026-10-31'});
});
test('cobertura nunca excede 90 dias e recusa datas inexistentes',()=>{
 assert.deepEqual(range.intersect([{since:'2026-01-01',until:'2026-11-12'}]),{since:'2026-08-15',until:'2026-11-12'});
 assert.equal(range.validPeriod({since:'2026-02-30',until:'2026-03-01'}),false);
});

