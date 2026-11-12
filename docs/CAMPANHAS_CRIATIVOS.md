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

Os dados diários permitem aplicar o mesmo período escolhido no Marketing sem
nova chamada à Meta pelo navegador. O status é o atual no instante da coleta,
não o status histórico em cada dia. O investimento e as métricas de cada cartão
correspondem ao próprio anúncio; não se repete o total da campanha em todos os
criativos. CPC = investimento dividido por cliques, exibindo indisponível quando
não há cliques. Alcance não é publicado como soma de dias/anúncios, porque a
mesma pessoa pode aparecer em vários deles. Não há percentuais de crescimento
inventados nem valores demonstrativos na publicação.

A seção existente “Campanhas ativas — Meta Ads” mantém sua regra de campanhas
atualmente ativas. Os totais da galeria podem diferir desse quadro quando o
filtro de status incluir anúncios pausados ou quando parte dos anúncios de uma
campanha estiver pausada.

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
