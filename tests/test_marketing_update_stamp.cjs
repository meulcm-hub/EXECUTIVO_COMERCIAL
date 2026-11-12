const test=require('node:test');
const assert=require('node:assert/strict');
const {formatTimestamp,createTracker}=require('../lcm-update-status.js');

test('formata a publicação real em Brasília e preserva virada do dia',()=>{
  assert.equal(formatTimestamp('2026-11-12T18:21:38.931143+00:00'),'12/11/2026 15:21');
  assert.equal(formatTimestamp('2026-11-12T01:05:00Z'),'11/11/2026 22:05');
  assert.equal(formatTimestamp('2026-11-12T06:00:00-03:00'),'12/11/2026 06:00');
});
test('data ausente ou inválida não vira horário de abertura',()=>{
  for(const value of [null,undefined,'','invalid','2026-11-12'])assert.equal(formatTimestamp(value),null);
  assert.deepEqual(createTracker().update(null,true),{datetime:'',text:'Indisponível',stale:false});
});
test('falha preserva última coleta válida e sucesso renova o horário',()=>{
  const tracker=createTracker();
  tracker.update('2026-11-12T18:21:00Z');
  assert.deepEqual(tracker.update(null,true),{datetime:'2026-11-12T18:21:00Z',text:'12/11/2026 15:21',stale:true});
  assert.equal(tracker.update('2026-11-12T11:00:00Z',true).datetime,'2026-11-12T18:21:00Z');
  assert.deepEqual(tracker.update('2026-11-12T21:01:00Z'),{datetime:'2026-11-12T21:01:00Z',text:'12/11/2026 18:01',stale:false});
});
test('consolidado publicado fornece data real se diário ainda não carregou',()=>{
  assert.deepEqual(createTracker().update('2026-11-12T11:00:00Z',true),{
    datetime:'2026-11-12T11:00:00Z',text:'12/11/2026 08:00',stale:true
  });
});
