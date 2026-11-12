/* Auditoria CV CRM: descriptografia local; nenhuma senha em armazenamento persistente. */
(function (root) {
  'use strict';
  const fields = ['idlead','cliente','empreendimento','project','origem','data_entrada',
    'data_venda','situacao_lead','situacao_precadastro','situacao_reserva'];
  function validate(report) {
    if (!report || report.schema_version !== 1 || !Array.isArray(report.rows) ||
        !report.rows.every(row => row && fields.every(key => typeof row[key] === 'string'))) {
      throw new Error('Auditoria recebida com formato inválido.');
    }
    return report;
  }
  function bytes(value) {
    if (typeof value !== 'string' || value.length > 48 * 1024 * 1024 ||
        !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value)) {
      throw new Error('Arquivo criptografado inválido.');
    }
    return Uint8Array.from(atob(value), c => c.charCodeAt(0));
  }
  async function decrypt(envelope, password) {
    if (!root.crypto?.subtle) throw new Error('Abra o dashboard por HTTPS em um navegador atualizado.');
    if (!envelope || envelope.encryption !== 'AES-256-GCM' ||
        envelope.kdf !== 'PBKDF2-SHA256' || envelope.iterations !== 250000) {
      throw new Error('Arquivo criptografado inválido.');
    }
    const salt = bytes(envelope.salt), nonce = bytes(envelope.nonce);
    const ciphertext = bytes(envelope.ciphertext);
    if (salt.length !== 16 || nonce.length !== 12 || ciphertext.length < 16) {
      throw new Error('Arquivo criptografado inválido.');
    }
    const material = await root.crypto.subtle.importKey('raw', new TextEncoder().encode(password),
      'PBKDF2', false, ['deriveKey']);
    const key = await root.crypto.subtle.deriveKey(
      {name:'PBKDF2', salt, iterations:envelope.iterations, hash:'SHA-256'},
      material, {name:'AES-GCM', length:256}, false, ['decrypt']);
    let plaintext;
    try {
      plaintext = await root.crypto.subtle.decrypt({name:'AES-GCM', iv:nonce}, key, ciphertext);
    } catch (_) {
      throw new Error('Senha incorreta ou arquivo danificado.');
    }
    return validate(JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(plaintext)));
  }
  root.CvAuditCrypto = Object.freeze({decrypt, validate});
})(globalThis);
