# Campanhas e criativos no Marketing

A seção abaixo da auditoria utiliza `data/marketing-creatives.json`, produzido
por `scripts/marketing_creatives.py` no GitHub Actions. O coletor usa o mesmo
secret `META_ACCESS_TOKEN` e as oito contas já vinculadas ao painel; não exige
upload manual de planilhas nem publicação do token no navegador.

## O que é coletado

- Catálogo de anúncios com status **efetivo atual**, campanha e mídias do criativo.
- Métricas no nível **anúncio/dia**, desde 01/01/2026 até o dia da coleta:
  impressões, cliques, investimento, formulários e conversas Meta.
- Miniaturas/imagens e vídeos disponíveis nas permissões do token. Carrosséis
  e variações dinâmicas podem conter diversas mídias. Se a Meta não liberar a
  reprodução direta, a miniatura e o link da publicação são mantidos quando
  disponíveis. Uma publicação da biblioteca de vídeos não é automaticamente
  tratada como um anúncio: a ligação vem do criativo vinculado ao anúncio.

Entram no arquivo os anúncios atualmente ativos (mesmo sem entrega) e todos
os anúncios com entrega no período anual. Anúncios antigos pausados sem
entrega em 2026 não exigem download de mídia nem ocupam a galeria. Os anúncios
pausados ou removidos que possuem métricas históricas continuam no arquivo. O catálogo é consultado sem um filtro de status computados; anúncios
históricos ausentes são conferidos individualmente pelo ID retornado nos
insights. Se o objeto também não retornar metadados de um anúncio histórico,
ele aparece com status `UNKNOWN`, nome/campanha dos insights e mídia
indisponível; seus resultados permanecem corretamente associados.

## Métricas e filtros

Empreendimento e período seguem sempre os filtros do topo do Marketing. Não
existe um segundo seletor de empreendimento nem opção para exibir anúncios
pausados na galeria: ela mostra somente os anúncios efetivamente ativos.
Campanha e tipo de mídia são refinamentos opcionais dessa mesma seleção.

Os dados diários permitem aplicar o mesmo período escolhido no Marketing sem
nova chamada à Meta pelo navegador. O status é o atual no instante da coleta,
não o status histórico em cada dia. O investimento e as métricas de cada cartão
correspondem ao próprio anúncio; não se repete o total da campanha em todos os
criativos. CPC = investimento dividido por cliques, exibindo indisponível quando
não há cliques. Alcance não é publicado como soma de dias/anúncios, porque a
mesma pessoa pode aparecer em vários deles. Não há percentuais de crescimento
inventados nem valores demonstrativos na publicação.

A seção existente “Campanhas ativas — Meta Ads” mantém sua regra de campanhas
atualmente ativas. Os totais da galeria podem diferir desse quadro quando parte
dos anúncios de uma campanha estiver pausada, porque a galeria inclui somente
os anúncios ativos.

## Contrato JSON (versão 1)

`schema_version`, `generated_at_utc`, `period.since`, `period.until`,
`currency: "BRL"`, `action_type`, `action_report_time`, `attribution`, `warning`,
`ads`.

Cada anúncio contém `ad_id`, `name`, `account_id`, `account_name`, `project`,
`campaign_id`, `campaign_name`, `status`, `media_type`, `image_url`, `video_url`,
`permalink_url`, `body`, `media`, `daily`. `project` usa a chave normalizada CV
quando existe vínculo; o filtro Meta deve usar `account_id`.

`media_type`: `image`, `video`, `carousel` ou `unknown`. Cada mídia contém
`type`, `image_url`, `video_url` e `permalink_url`. Múltiplas variações podem
aparecer como `carousel`. Campos de URL indisponíveis são strings vazias.

`daily` é uma lista de objetos `{date, impressions, clicks, spend, form_leads,
messages}`. `spend` é uma string decimal, preservando precisão na coleta.
Não existem linhas duplicadas para o mesmo anúncio/dia.

## Segurança e atualização

O coletor publica somente uma projeção explícita: não grava resposta bruta,
token, cabeçalhos, IDs de leads, telefones nem emails. URLs aceitas usam HTTPS
em domínios Meta/CDN; URLs com parâmetros de autenticação são rejeitadas.
As fontes dos vídeos são consultadas também pela biblioteca `/act_ID/advideos`,
no contexto da conta relacionada ao empreendimento, com consulta individual
como alternativa. Falta de permissão mantém a miniatura e o link da publicação.

Assinaturas próprias de CDN são preservadas porque permitem carregar a mídia
e podem expirar; cada coleta renova as URLs disponíveis. O navegador jamais
consulta a Graph API usando o secret.

As consultas de insights são divididas em meses para manter a paginação
limitada e reprocessam o histórico anual. O arquivo é substituído de forma
atômica somente depois do término das métricas de todas as contas. Erros de
permissão de uma mídia individual preservam as demais mídias e resultados;
erros nas contas, catálogo ou métricas preservam o arquivo publicado anterior.

Validação local sem credenciais:

```sh
python -m unittest discover -s tests -p 'test_marketing_creatives.py'
```

## Reconciliação Meta × CV CRM — 13/11/2026

A apresentação foi ajustada para não comparar subconjuntos diferentes como se fossem o mesmo total:

- **Marketing principal:** campanhas atualmente `ACTIVE`, somadas ao longo do período selecionado. Mensagens (`onsite_conversion.messaging_conversation_started_7d`) são contadas independentemente de o nome da campanha conter WADS/WhatsApp. Formulários usam `onsite_conversion.lead_grouped`. Campanhas de reconhecimento permanecem no gasto total.
- **Campanhas e Criativos:** na seleção sem filtro extra por campanha/mídia, os KPIs de investimento, formulários e WhatsApp passam a usar **exatamente o mesmo arquivo de campanhas ativas** (`data/marketing-campaigns.json`), com os mesmos IDs de conta e intervalo. Impressões, cliques, CPC e a lista de criativos continuam sendo **somente anúncios com status ACTIVE**, provenientes de `data/marketing-creatives.json`; a diferença de escopo é visível.
- Selecionar uma campanha ou tipo de mídia refina os criativos e seus indicadores. Essa seleção não deve ser confundida com o total de campanhas ativas.
- **CV CRM:** prospects são registros únicos, cuja data e origem seguem critérios próprios da safra. Resultados Meta são eventos atribuídos, não pessoas únicas. A interface agora confronta os dois números com nota explícita, sem forçar igualdade.
- Clique total das contas não pode ser usado como denominador de conversão dos resultados exclusivos das campanhas ativas. A taxa misturada foi retirada da apresentação.
- As coletas de campanhas e criativos são independentes; sua última atualização e eventual defasagem devem continuar visíveis.

Snapshot da fonte real (01/01/2026 a 12/11/2026, quatro contas vinculadas): 5.156 formulários e 876 conversas em campanhas ativas, total 6.032 eventos. A regra antiga de filtro pelo nome da campanha mostrava apenas 568 conversas. O funil CV registrava 5.908 prospects, número que não é comparável diretamente.

Testes adicionados em `tests/test_marketing_meta_alignment.cjs`; workflow `marketing-meta-alignment.yml`.
