# Auditoria pública automática do Marketing

A auditoria de clientes no Marketing abre automaticamente, sem senha e sem
importação de planilhas, seguindo o acesso público do relatório Executivo.
A publicação dos nomes e das colunas da tabela no GitHub Pages foi solicitada
pelo proprietário. Qualquer pessoa com acesso ao site ou repositório público
pode consultar esses dados.

## Dados publicados

O arquivo `data/cv-audit.json` contém somente Cliente, Empreendimento, Origem,
Data da Entrada, Data da Venda, Situação Lead, Situação Pré-Cadastro,
Situação Reserva e a chave normalizada do empreendimento usada pelos filtros.
IDs de leads/reservas, e-mails, telefones, documentos, tipo de entrada e payloads
originais da API são descartados por uma projeção positiva antes da publicação.

O coletor mantém os vínculos por IDs na memória e em um arquivo temporário do
runner para consolidar o funil. Somente o relatório reduzido da auditoria e os
totais agregados entram no commit público. Não há artefato com o JSON bruto.

## Atualização automática

O workflow **LCM - Funil comercial CV CRM por safra** consulta as APIs com os
secrets CVCRM_DOMINIO, CVCRM_EMAIL e CVCRM_TOKEN já existentes. Após a coleta,
`scripts/publish_cv_audit.py` valida e publica somente as colunas autorizadas.
A senha CV_AUDIT_PASSWORD não é usada nas próximas coletas.

O dashboard mantém os filtros de empreendimento e período de entrada e oferece
o filtro Situação Reserva. Esse filtro altera apenas as linhas da auditoria;
os totais do funil continuam representando a safra completa selecionada.

## Transição do formato anterior

O workflow **LCM - Disponibilizar auditoria pública existente** pode aproveitar
a última coleta criptografada já existente para disponibilizar a auditoria sem
aguardar outra leitura completa das APIs. Ele usa o secret antigo somente para
essa conversão no runner e publica a mesma projeção mínima.

Se a auditoria pública já existir, a migração não a sobrescreve. Se não houver
arquivo anterior ou secret disponível, ela é ignorada e a próxima coleta normal
gera os dados. Nenhuma senha precisa ser digitada na página. O arquivo
criptografado antigo pode continuar no histórico do Git sem ser usado pelo site.

## Verificação

`python -m unittest discover -s tests -p 'test_publish_cv_audit.py'` cobre
projeção dos campos, exclusão de identificadores e contatos, validação de datas,
dados malformados, escrita do arquivo e conversão do formato criptografado.
A biblioteca cryptography é necessária apenas para a migração do formato antigo.

