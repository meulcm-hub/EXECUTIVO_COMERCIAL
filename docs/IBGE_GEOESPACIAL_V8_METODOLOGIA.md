# IBGE 2022 — integração geoespacial V8

## Execução com arquivos reais
Workflow: https://github.com/meulcm-hub/EXECUTIVO_COMERCIAL/actions/runs/43477787826
Malhas oficiais por UF (IBGE 2022) e agregados básicos revistos em 20/05/2026 foram realmente descarregados e processados.
14 empreendimentos cadastrados; 2 candidatos de coordenadas não verificadas (Monttebelo e Turquesa Parque), 12 aguardando centro geográfico próprio.
Para os dois candidatos, a revisão calculou os raios 1, 3, 5, 10 km em artifacts/ibge-sector-preview.json. Não são resultados publicáveis.

## Arquivos oficiais e variáveis
- Agregados básicos Censo 2022, revistos em 20/05/2026: https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/Agregados_por_Setor_csv/Agregados_por_setores_basico_BR_20260520.zip
- Malha por UF: https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/setores/shp/UF/
- Colunas: CD_SETOR, CD_UF; v0001 = total de pessoas; v0007 = domicílios particulares ocupados.
- Características domiciliares revisto 21/10/2026 (schema conferido, não usado no cálculo): https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/Agregados_por_Setor_csv/Agregados_por_setores_caracteristicas_domicilio1_BR_20261021.zip

## Metodologia
Os círculos são construídos em projeção métrica azimutal equidistante no centro de cada terreno, raios 1/3/5/10 km.
Fração = área(setor ∩ círculo) / área(setor). População estimada = Σ(população oficial × fração). Domicílios estimados = Σ(domicílios particulares ocupados × fração).
A distribuição dentro do setor é presumida uniforme; trata-se de uma estimativa, não de observação domiciliar. Densidade é o total estimado / área circular em km².
Setores sem variáveis oficiais são classificados como cobertura incompleta, nunca zerados.
Geometrias publicadas são o setor oficial recortado ao círculo. Cores baixa/média/alta representam DENSIDADE populacional, não número de compradores nem mercado potencial.
Raios próximos à divisa entre estados (por exemplo, Extrema MG/SP) precisam de setores de todas as UFs intersectadas.

## Bloqueios e salvaguardas
Os candidatos de Monttebelo e Turquesa Parque continuam verified:false. Confirmar individualmente o centro físico do terreno; coordenadas de endereço não garantem centro do terreno.
Flamboyant/Jatobá e Ipê/Jacarandá são lotes vizinhos distintos e não podem compartilhar automaticamente centro geográfico.
O comando --review gera apenas artefatos de prévia; --publish exige centro verified:true, verified_by, verified_at e verification_evidence.
O workflow manual ibge-geospatial-publish.yml gera os artefatos, mas não os integra automaticamente à branch principal sem revisão.
O V8 só mostra polígonos setoriais para centro validado, projeto, raio e ano 2022 correspondentes.

## Renda e potencial de mercado
Rendimento do responsável pelo domicílio NÃO equivale a renda domiciliar total. Não é metodologicamente válido preencher o cartão renda domiciliar a partir desse indicador sem identificação explícita.
Potencial de mercado requer contagem setorial de domicílios compatíveis com condições do empreendimento e critério documentado, não população total ou fator arbitrário.
Sem variável oficial apropriada e centros verificados, esses KPIs permanecem indisponíveis. Não usar renda/idade/gênero para segmentação discriminatória de habitação.

## Próximas validações necessárias
1. Centro de cada terreno comprovado por mapa/croqui georreferenciado e revisão independente.
2. Processar os 14 locais aprovados, incluindo cruzamentos entre UFs quando aplicável.
3. Conferir o GeoJSON por raio e aprovar publicação de dados agregados.
4. Completar variáveis de rendimento/condições do produto para cálculo real de potencial.
