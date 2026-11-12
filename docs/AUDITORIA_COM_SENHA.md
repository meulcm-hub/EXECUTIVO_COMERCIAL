# Auditoria automática com senha no GitHub Pages

A coleta continua no workflow **LCM - Funil comercial CV CRM por safra**.
Os totais permanecem públicos. Os clientes só aparecem após abrir a auditoria
com a senha, no próprio dashboard. Não há planilha para importar nem servidor Render.

## Ativação única

1. No repositório, abra Settings → Secrets and variables → Actions.
2. Clique em New repository secret.
3. Nome: `CV_AUDIT_PASSWORD`. Valor: uma senha aleatória e exclusiva com pelo menos
   16 caracteres, preferencialmente gerada e guardada em um gerenciador de senhas.
   Não coloque a senha no código, em issues, em comentários ou no chat.
4. Integre a proposta e acompanhe o workflow do funil em Actions. Se necessário,
   execute Run workflow na branch main.
5. Abra marketing.html, informe a mesma senha e clique em Abrir auditoria.

As credenciais CVCRM_DOMINIO, CVCRM_EMAIL e CVCRM_TOKEN continuam nos secrets
já usados pela coleta. A ativação só termina após o workflow concluir com sucesso.

## Comportamento

- O arquivo individual bruto permanece no diretório temporário do runner.
- Apenas `data/cv-audit.enc.json`, criptografado com AES-256-GCM e chave derivada
  por PBKDF2-SHA256 (250.000 iterações e salt aleatório), é publicado.
- O navegador solicita apenas o arquivo criptografado. A senha é usada localmente,
  não é enviada ao GitHub e não é guardada em localStorage ou sessionStorage.
- Enquanto a auditoria está aberta, a senha permanece na memória da página
  para abrir a atualização automática. Fechar auditoria limpa essa referência e
  os clientes da tela. Recarregar ou fechar a página exige abrir novamente.
- Os filtros de empreendimento e Data da Entrada mantêm a lógica do funil.
- Sem o secret, o workflow publica um marcador de indisponibilidade em vez de
  manter uma versão antiga da auditoria como se estivesse atualizada.
- O GitHub Pages não bloqueia os totais nem o HTML: a senha protege os dados
  individuais por criptografia. Uma senha forte é necessária porque o arquivo
  criptografado pode ser baixado publicamente e submetido a tentativas offline.
- Trocar a senha do secret e executar a coleta altera a chave das próximas
  publicações. Não revoga cópias ou versões antigas já baixadas.

## Validação

`node --test tests/test_audit_crypto.cjs` verifica interoperabilidade entre o
criptografador Python e Web Crypto, senha incorreta, adulteração e formato inválido.
Requer Python com cryptography e Node.js com Web Crypto.
