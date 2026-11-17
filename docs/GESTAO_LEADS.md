# Gestão de Leads — integração e critérios

## Telas e dados

`leads.html` e `lcm-leads.*` compõem o módulo comercial, isolado das outras páginas.
A interface anterior fica em `leads-auditoria.html` e `lcm-leads-audit.*`.
O arquivo `data/leads-all-summary.json` permanece como fonte pública validada,
sem nomes, IDs pessoais ou contatos. Nenhuma coleta existente foi modificada.

| Tela | Fonte disponível | Limitação explícita |
| --- | --- | --- |
| Visão Geral | Base integral CVDW validada, enriquecida pela API comercial | Métricas de situação atual da safra de cadastro; não são eventos históricos |
| Lista de Leads | Carteira autenticada de comercial/leads | Exige servidor Python com CVCRM_* e AUDIT_USER/AUDIT_PASSWORD |
| Pipeline | Situações atuais, 9 grupos | Leitura; não há endpoint de transição comprovado |
| Origem e Canais | Origem oficial e mídias do lead | Sem atribuição por campanha/CPL do mesmo recorte |
| Desempenho | Corretor explícito da carteira privada | Sem equipe ou SLA inferidos |
| Atendimento | Datas explícitas retornadas pela API | Sem respostas, atrasos ou tempo médio calculados por situação |

## Endpoints existentes preservados

- `/api/v1/cvdw/leads`: pagina/registros_por_pagina, histórico integral.
- `/api/v1/comercial/leads`: limit/offset, cadastro e dimensões comerciais.
- `/api/v1/cvdw/leads/visitas` e `/api/v1/cvdw/leads/tarefas`: coletor do funil.
- `/api/v1/comercial/precadastro` e `/api/v1/cvdw/reservas`: coletor do funil.
- Rotas preexistentes `/api/funil/publico` e `/api/funil/privado` preservadas.

## Carteira privada nova

`GET /api/leads/carteira` e `/leads_privado.html` usam o mesmo HTTP Basic
já existente no servidor. A primeira consulta agenda uma coleta de todas as
páginas comerciais. Enquanto incompleta, retorna 202 sem lista parcial.
Total variável, ID duplicado ou página vazia interrompem a publicação.
Dados só existem em memória, com Cache-Control private,no-store e sem CORS.
A fonte pública não contém nomes. É necessário abrir a página privada no mesmo
servidor Python; GitHub Pages não fornece execução Python nem autenticação.
Não há URL de servidor privado configurada no repositório para o botão público.

A projeção privada permite somente dois nomes do lead e do corretor, ID interno,
data de cadastro, empreendimento, origem, mídia e situação. Telefone, CPF, e-mail,
endereço, observações livres e nome completo são descartados. Histórico livre não
é retornado, pois pode conter contatos e nomes de terceiros.

## Definições comerciais

- Captados: cadastro original na janela filtrada.
- Ativos: situações abertas reconhecidas, excluindo venda/perdido; situações
  desconhecidas não são classificadas como ativas.
- Oportunidades: status atuais qualificado, agendamento, visita, CAD/A,
  pré-cadastro, análise de crédito, aprovado e reserva.
- Vendas: leads da safra que estão em VENDA/VENDA REALIZADA. Não é número de
  contratos assinados no período. A série de vendas por data fica indisponível.
- Conversão: leads da safra atualmente em venda / captados da mesma safra.
- Comparação: janela de cadastro anterior de igual duração, usando situação atual
  nos dois grupos. Não representa uma fotografia histórica da carteira anterior.
- Meta Ads/Google Ads são agrupamentos de origem declarada. Não comprovam gasto
  nem vínculo com anúncio pago. Busca Compartilhada e WhatsApp Facebook seguem a
  classificação LCM já aprovada. A origem CV CRM original permanece nos filtros.
- Ausência de status para uma etapa inteira: “Etapa sem dados”, em vez de zero.

## Pendências para operação completa

Validar a hospedagem privada e suas credenciais no ambiente de produção; confirmar
campos de contato/interação e paginação comercial em execução real; integrar tarefas,
agendamentos e equipes à carteira individual; confirmar contrato e permissões de
transição de etapas antes de qualquer escrita; atribuir campanha/investimento por ID
antes de calcular CPL neste módulo. Sem dados sintéticos nos painéis publicados.
A referência visual original não foi recuperada: composição segue o briefing textual.

## Validação

`node --test tests/test_leads_management.cjs` e testes legados de classificação e
conferência; `python -m unittest discover -s tests -p 'test_leads_operations.py'`;
testes de rotas privadas requerem dependências de requirements.txt e httpx.


## Atualização: carteira pública no GitHub (17/11/2026)

Por orientação do usuário, a carteira também funciona sem servidor externo.
O workflow leads-full-history coleta os dados com CVCRM_* em GitHub Secrets,
reduz os nomes e publica `data/leads-roster.json` junto ao agregado, somente após
validar todas as páginas. A projeção autoriza exclusivamente name, date, project,
origin, origin_name, lead_media, status e owner. Nome e responsável têm no máximo
dois termos. CPF, telefone, e-mail, ID interno, endereço e histórico livre nunca
são gravados nesse arquivo. O arquivo é público: nome reduzido e vínculo comercial
não são considerados anônimos. A autorização do usuário não foi interpretada como
permissão para publicar contatos. O token permanece exclusivamente no Actions.

A interface pública lê esse arquivo para lista, cartões, pesquisa, ordenação,
paginação e exportação. Até a primeira coleta completa, informa carteira em
atualização. O botão Atualizar carteira recarrega a última publicação; não inicia
chamadas ao CV CRM pelo navegador e não altera etapas. A carteira é atualizada na
mesma agenda já existente do histórico completo, sem nova infraestrutura.


## Histórico operacional por cliente

O coletor integral consulta as quatro fontes CVDW de interações, tarefas,
visitas e histórico de situações, com paginação de 500 registros e limite de
referência fixado no início da coleta. A coleta falha se os totais mudarem,
se uma página se repetir ou se a vinculação não puder ser comprovada.

Os IDs são usados somente em memória para relacionar os registros. A carteira
pública v2 usa uma chave HMAC opaca para consultar arquivos particionados de
histórico. Nenhum ID do CV, texto livre, áudio, telefone, CPF ou e-mail entra
nesses arquivos. Clientes com nomes iguais mantêm históricos separados.

A ficha exibe todos os eventos ativos disponíveis, em ordem decrescente,
com carregamento sob demanda e paginação visual de 50 registros. Uma mudança
de etapa não comprova atendimento. Último registro de contato considera a
data de cadastro de interações dos tipos de contato; não comprova atendimento
ou resposta. Próxima ação usa a tarefa pendente/em andamento com menor prazo,
incluindo atrasadas; tarefas concluídas e canceladas não entram. Ausência de
prazo ou situação reconhecida não cria agendamento. Indicadores de SLA seguem
indisponíveis até existirem regras e dados suficientes.

A publicação valida a correspondência entre a quantidade de eventos por lead
e seus arquivos históricos. A carteira anterior permanece no site até a
coleta integral e todas as verificações terminarem.


### Correção da carga com CRM em movimentação (17/11/2026)

A Gestão de Leads utiliza os campos documentados da própria fonte CVDW
(nome, corretor, origem_nome, midia_original e midia_ultimo). A varredura da
listagem comercial viva por offset foi retirada do caminho de publicação,
pois seu total mudou durante a leitura e interrompeu a carga em 17/11.
O coletor comercial anterior permanece disponível para seus demais usos.

A base e os quatro históricos recebem o mesmo limite ate_data_referencia.
Nomes permanecem reduzidos a dois termos. As mídias conhecidas nesta fonte
são a original e a última; não se declara que representem todas as mídias
que possam estar vinculadas ao lead no endpoint comercial. O metadado
explicitamente informa dimension_source=cvdw; as contagens legadas da
consulta comercial não são preenchidas com números de outra fonte.

Totais, paginação, IDs, datas e vínculo da carteira com os históricos
continuam validados antes da publicação. A consulta inicial comprova os
campos CVDW e o total antes de iniciar a leitura dos históricos.
