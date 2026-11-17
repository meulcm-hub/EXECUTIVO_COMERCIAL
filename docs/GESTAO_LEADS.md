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
