# Público Comprador — Potencial da Região (IBGE) V7

## Interface e fonte de verdade
A aba foi reconstruída seguindo a referência visual fornecida: filtro interno (empreendimento/raio/cidade/bairro), 5 KPIs, comparação e insights, mapa interativo, 2 painéis de campanhas e botão para gerar plano exportável via impressão em PDF.

**Não alterar outras abas/páginas:** o módulo reaproveita a shell e a base do Público Comprador, carregando um JS V7 isolado e CSS escopado a #audience. Executivo Comercial, Marketing, Leads e Auditoria ficam inalterados.

## Fontes atualmente ligadas
- Endereço físico: config/ibge-project-addresses.json, 14 empreendimentos, informado pela LCM em 13/11/2026. Alguns terrenos adjacentes compartilham endereço textual, mas exigem centros diferentes; endereço textual **não equivale a coordenada validada**.
- Compradores: objeto agregado AUD do Público Comprador no index.html (perfil/renda/idade/cidade) e data/buyer-locations.json (localidades agregadas, com supressão de contagens abaixo de cinco). O total por cidade/bairro do KPI é derivado apenas dos grupos geográficos disponíveis, não de todo o CRM. Os agregados por renda/idade usam seu próprio denominador e não são filtráveis por bairro ou data sem vínculo individual.
- Vendas: base SALES existente; preservada sem modificações. Os filtros globais de vendas permanecem em outras abas, mas são ocultados **somente** nesta aba IBGE para reproduzir a barra interna da referência e impedir duplicação de filtros.
- IBGE Censo Demográfico 2022: API de Localidades por nome + UF, API de Agregados, tabela **4714** variáveis 93 (população residente), 6318 (área territorial, km²), 614 (densidade municipal); tabela **4712**, variável 381 (domicílios particulares permanentes ocupados). Dados municipais são rotulados **município inteiro**, nunca como entorno.
- Meta Ads: data/marketing-campaigns.json é lido para identificar presença da base agregada. **Não** se atribuem campanhas/resultados a um empreendimento sem identificador/crosswalk validado. Google Ads: sem integração comprovada; só recomendações estratégicas.

## Indicadores e cálculos
- População: tabela 4714 IBGE para o município. Quando houver contexto setorial aprovado para o raio, substitui por população estimada **do raio**, rotulada assim.
- Domicílios: tabela 4712 IBGE para município inteiro, ou estimativa setorial do raio se validada.
- Rendimento domiciliar: **pendente** até bases censitárias setoriais com variável apropriada, ano, universo e método verificados. Não trocar rendimento por pessoa por rendimento familiar.
- Compradores LCM (origem geográfica): soma dos grupos válidos de localidades da fonte agregada, incluindo apenas contagens de pelo menos 5. Filtros de cidade/bairro restringem os grupos expostos; o valor **não** corresponde ao universo completo de pessoas únicas do CRM.
- Potencial de mercado: **pendente**. O código só admite valores fornecidos em data/ibge-project-context.json, com year=2022, method=sector_intersection_area_weighted, center.verified=true, center.source="CV CRM", center.precision="address_number", marketMethod="income_compatible_households_documented" e marketPotential numérico.
- A metodologia planejada do potencial é o número de **domicílios** elegíveis por localização, renda familiar **regional** e condições do produto, deduplicados e acompanhados de hipóteses e incerteza, sem equiparar população a compradores. É proibido criar multiplicadores arbitrários ou converter o potencial em perfil de segmentação de anúncios.
- Perfil LCM: porcentagem count/sum(contagens válidas da mesma categoria). Não comparar quantitativamente renda do LCM a uma população regional sem faixas censitárias correspondentes.
- Insights: maior cidade e faixa de renda historicamente classificadas, com denominadores explícitos; contexto municipal quando a API responder; nenhum dado inventado.

## Mapa de Oportunidades
- OpenStreetMap / Leaflet local do repositório (scripts e estilos locais).
- Camada cidades: data/buyer-locations.json, pontos no nível de centro municipal; círculos dimensionados por contagem (não heatmap setorial).
- Camada bairros: mesma fonte, pontos aproximados; desligada por padrão.
- Setores IBGE: só carrega data/ibge-opportunity-map.geojson quando FeatureCollection e metadata.source="IBGE", metadata.year=2022 e todas as feições têm ibge_sector_code. GeoJSON ainda não foi publicado.
- Localização exata e círculo 1/3/5/10 km: só são exibidos se data/ibge-project-context.json possuir centro aprovado e verificável por empreendimento. Os centros não são inferidos dos compradores ou dos municípios.
- Controles de camadas e legendas, inclusive estados indisponíveis, estão na interface.

## Recomendações de publicidade habitacional
- São **propostas**, não campanhas executadas e não resultados observados.
- Meta Ads: formulário/WhatsApp, criativos reais, mensagens verificadas, testes geográficos que respeitem a categoria habitacional, métricas CPL/lead válido/visita/venda auditada.
- Google Ads: pesquisa por intenção, nomes do empreendimento e da cidade, conteúdo real para YouTube, landings por empreendimento, CTR, CPL e atribuição.
- Não utilizar idade, sexo, raça, cor, religião, estado civil, renda individual ou qualquer característica protegida como critério discriminatório de segmentação ou exclusão. Revisar políticas de plataforma e legislação aplicáveis antes de lançar campanhas.
- O plano completo é gerado **localmente no navegador** a partir de informações agregadas (sem dados pessoais), e a opção "Salvar plano em PDF" utiliza o diálogo de impressão do navegador.
- Orçamento, ROAS, CPA ou metas numéricas não são recomendados quando não existem dados auditados de custo e conversão por empreendimento.

## Limitações e próxima etapa
1. Validar coordenada individual de cada terreno e sua precisão.
2. Processar malhas do Censo 2022 e dados de domicílios/rendimentos por setor; distribuir população/domicílios pela interseção espacial com cautela e método explícito.
3. Publicar dados setoriais auditados somente após validação (data/ibge-project-context.json e GeoJSON).
4. Auditar IDs de empreendimentos para relacionar histórico de Meta e futuramente Google Ads.
5. Testar manualmente o visual em desktop, tablet e celular e exportar PDF no Chrome; validações estáticas não substituem esse passo.

## Referências
- IBGE / SIDRA tabela 4714: https://sidra.ibge.gov.br/tabela/4714
- IBGE / SIDRA tabela 4712: https://sidra.ibge.gov.br/tabela/4712
- API Localidades: https://servicodados.ibge.gov.br/api/v1/localidades/municipios
- Política Google Ads sobre anúncios habitacionais: https://support.google.com/adspolicy/answer/16701755
- Política Meta publicidade e habitação: https://about.fb.com/news/2019/03/protecting-against-discrimination-in-ads/
