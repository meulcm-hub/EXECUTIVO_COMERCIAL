const test = require('node:test');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const {mkdtempSync, writeFileSync, readFileSync, rmSync} = require('node:fs');
const {tmpdir} = require('node:os');
const path = require('node:path');
require('../audit-crypto.js');

const password = 'senha-ficticia-somente-teste-2026';
const report = {schema_version:1, period:{since:'2026-11-01',until:'2026-11-12'}, rows:[{
  idlead:'1', cliente:'Cliente fictício çã', empreendimento:'Teste', project:'teste',
  origem:'Google', data_entrada:'2026-11-01', data_venda:'2026-11-12',
  situacao_lead:'Atendimento', situacao_precadastro:'Aprovado', situacao_reserva:'Vendida'
}]};
function encryptedFixture() {
  const directory = mkdtempSync(path.join(tmpdir(), 'cv-audit-test-'));
  try {
    const input = path.join(directory,'input.json'), output = path.join(directory,'output.json');
    writeFileSync(input, JSON.stringify(report));
    const result = spawnSync(process.env.PYTHON || 'python', [
      path.join(__dirname,'../scripts/encrypt_cv_audit.py'), input, output
    ], {encoding:'utf8', env:{...process.env, CV_AUDIT_PASSWORD:password}});
    assert.equal(result.status,0,result.stderr);
    const envelope = JSON.parse(readFileSync(output,'utf8'));
    assert.ok(!JSON.stringify(envelope).includes(report.rows[0].cliente));
    assert.ok(!JSON.stringify(envelope).includes(password));
    return envelope;
  } finally { rmSync(directory,{recursive:true,force:true}); }
}
const envelope = encryptedFixture();
test('Python AES-GCM/PBKDF2 abre no Web Crypto com Unicode', async()=>{
  assert.deepEqual(await CvAuditCrypto.decrypt(envelope,password),report);
});
test('senha incorreta não libera dados', async()=>{
  await assert.rejects(CvAuditCrypto.decrypt(envelope,'senha-errada'),/Senha incorreta/);
});
test('arquivo alterado não libera dados', async()=>{
  const changed = {...envelope};
  const bytes = Buffer.from(changed.ciphertext,'base64'); bytes[0]^=1;
  changed.ciphertext = bytes.toString('base64');
  await assert.rejects(CvAuditCrypto.decrypt(changed,password),/arquivo danificado/);
});
test('parâmetros inválidos são recusados antes de derivar chave', async()=>{
  for(const changed of [{iterations:1},{iterations:999999999},{nonce:'YWJj'},
    {salt:'não-base64'},{encryption:'AES-CBC'},{ciphertext:''}]) {
    await assert.rejects(CvAuditCrypto.decrypt({...envelope,...changed},password),/inválido/);
  }
});
test('JSON individual sem campos obrigatórios é recusado',()=>{
  assert.throws(()=>CvAuditCrypto.validate({schema_version:1,rows:[{}]}),/inválido/);
});
