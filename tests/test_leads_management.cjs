const {test}=require('node:test');const assert=require('node:assert/strict');const M=require('../lcm-leads-model.js');
test('situação atual não cria vendas, atendimento ou passagens históricas',()=>{const rows=[{status:'NOVO LEAD',count:3},{status:'DESCARTADO',count:8},{status:'VENDA REALIZADA',count:2},{status:'ANÁLISE DE CRÉDITO',count:4},{status:'SEM CLASSIFICAÇÃO',count:7}];assert.deepEqual(M.metrics(rows),{captured:24,active:7,opportunities:4,sales:2,conversion:2/24*100,unclassified:7});});
test('filtros combinados e safra anterior de igual tamanho',()=>{const f={since:'2026-03-01',until:'2026-03-31',project:'Ipê',origin:'Facebook',status:''};const rows=[{date:'2026-03-01',project:'Ipê',origin_name:'Facebook',count:4},{date:'2026-02-28',project:'Ipê',origin_name:'Facebook',count:6},{date:'2026-03-01',project:'Jatobá',origin_name:'Facebook',count:2}];assert.equal(M.total(M.filter(rows,f)),4);assert.equal(M.previous(f).since,'2026-01-29');assert.equal(M.previous(f).until,'2026-02-28');assert.equal(M.previous({...f,since:'2026-04-01'}),null);});
test('nomes e CSV não expõem sobrenomes adicionais nem executam fórmulas',()=>{assert.equal(M.shortName('Maria Silva Oliveira'),'Maria Silva');assert.ok(M.csv([['=1+2','a"b']]).includes("'="));assert.ok(M.csv([['a"b']]).includes('a""b'));});
test('sem denominador anterior não mostra comparação fictícia',()=>{assert.equal(M.delta(4,0).value,null);assert.equal(M.delta(0,0).value,0);});
test('canais preservam whatsapp facebook e busca compartilhada',()=>{assert.equal(M.channel({origin:'BC'}),'Meta Ads');assert.equal(M.channel({origin:'GE',lead_medias:['WhatsApp Facebook']}),'Meta Ads');assert.equal(M.origin({origin:'GE',origin_name:'Painel Gestor'}),'Painel Gestor');});
test('status de tarefas distingue ausência confirmada, prazo, falta de data e fonte não consultada',()=>{
 const fs=require('node:fs'),vm=require('node:vm');
 const source=fs.readFileSync(require.resolve('../lcm-leads.js'),'utf8');
 const fn=vm.runInNewContext('('+source.match(/function taskStatus\([\s\S]*?\n\}/)[0]+')');
 const now=Date.parse('2026-11-18T12:00:00Z');
 const task=(date,state='Pendente')=>({kind:'task',state,scheduled_at:date});
 assert.equal(fn({},undefined,now),'Tarefas ainda não verificadas');
 assert.equal(fn({},[],now),'Não possui tarefa');
 assert.equal(fn({},[task(null,'Concluída')],now),'Não possui tarefa');
 assert.equal(fn({},[task(null)],now),'Possui tarefa sem data');
 assert.equal(fn({},[task('2026-11-19T12:00:00Z')],now),'Possui tarefa em dia');
 assert.equal(fn({},[task('2026-11-17T12:00:00Z'),task('2026-11-19T12:00:00Z')],now),'Possui tarefa atrasada');
 assert.equal(fn({next_action_at:'2026-11-17T12:00:00Z'},undefined,now),'Possui tarefa atrasada');
});

test('pipeline segue as seis etapas comerciais e limites das cadências',()=>{
 assert.deepEqual(M.stages,['Novo Lead','Em Atendimento','Agendamento','Visita','Análise de Crédito','Venda']);
 for(const status of ['PROSPECÇÃO','NOVO LEAD'])assert.equal(M.stage(status),'Novo Lead');
 for(let i=1;i<=7;i++)assert.equal(M.stage('CAD/C '+i),'Em Atendimento');
 for(let i=1;i<=20;i++)assert.equal(M.stage('CAD/A '+i),'Agendamento');
 assert.equal(M.stage('AGENDAMENTO'),'Agendamento');assert.equal(M.stage('Visita'),'Visita');
 assert.equal(M.stage('ANÁLISE DE CRÉDITO'),'Análise de Crédito');assert.equal(M.stage('VENDA REALIZADA'),'Venda');
 for(const status of ['CAD/A 0','CAD/A 21','CAD/C 8','QUALIFICADO','PRÉ-CADASTRO','APROVADO','RESERVA','VENDA'])assert.equal(M.stage(status),null);
 assert.equal(M.stage('DESCARTADO'),'Perdido');
});
