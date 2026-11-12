# Atualizações programadas do Marketing

As coletas automáticas iniciam todos os dias às **06h, 12h e 18h**, no
horário de Brasília (`America/Sao_Paulo`, UTC-3). O GitHub Actions usa UTC;
por isso os quatro workflows usam `0 9,15,21 * * *`.

| Rotina | Dados publicados |
| --- | --- |
| `marketing-consolidate.yml` | Meta Ads, calendário e campanhas |
| `marketing-cv-conversions.yml` | Cadastros e retornos do CV CRM |
| `marketing-cv-funnel.yml` | Funil e auditoria individual do CV CRM |
| `marketing-creatives.yml` | Imagens, vídeos e desempenho dos anúncios |

Os horários indicam o início das coletas. A publicação ocorre depois da
consulta e validação; o GitHub Actions pode colocar uma execução em fila.
Os diagnósticos manuais e a migração da auditoria continuam sem agendamento.

O rodapé do Marketing informa o dia e a hora reais da última coleta Meta
publicada, usando `generated_at_utc`, convertido para Brasília. Abrir a
página ou alterar filtros não muda essa informação. Se a consulta falhar,
a última coleta carregada continua identificada; não se simula uma nova
atualização com o horário do navegador.

As rotinas dependem dos secrets válidos da Meta e do CV CRM. Quando a API
recusa uma credencial ou uma coleta fica incompleta, a publicação anterior
é preservada.

Este agendamento cobre as fontes automáticas existentes. A base de vendas,
estoque, financeiro e público comprador do Executivo está incorporada no
relatório e ainda não possui um coletor automático próprio.
