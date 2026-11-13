# IBGE V8.1 — correção incremental em 13/11/2026

## O que foi publicado
- Base nacional municipal oficial do IBGE Censo 2022: `data/ibge-municipal-responsible-income.json` (5.570 municípios), produzida por `scripts/ibge_publish_municipal_income.py` e atualizada automaticamente pelo workflow `ibge-municipal-income.yml`.
- Variável V06004 do IBGE: **rendimento nominal médio mensal das pessoas responsáveis pelo domicílio com rendimento**. É incorreto tratá-la como renda domiciliar/familiar média. A interface da V8 foi renomeada, e o indicador tem fonte explícita.
- Mapa: adicionalmente consulta a malha municipal oficial do IBGE via `/api/v3/malhas/municipios/{codigo}` e oferece controle de camada de limite municipal. É malha MUNICIPAL, e não substitui polígonos de setor ou círculo centrado no empreendimento.
- Comparativo: exibe lado a lado a contagem de domicílios municipais IBGE e os compradores LCM geolocalizados disponíveis, com razão descritiva e alerta de universos distintos. **Não** é uma taxa de penetração nem uma comparação de composição de renda.

## Limitações que permanecem
- O conjunto `data/ibge-project-context.json` não pode ser publicado sem centros de terreno individualmente aprovados. Apenas dois pontos são candidatos, sem verificação, e doze aguardam localização específica. Não há publicação do GeoJSON setorial por raio, por motivo de integridade espacial.
- Renda média do responsável não permite inferir renda familiar total, faixa de renda dos domicílios nem elegibilidade de financiamento.
- O **potencial de compradores elegíveis** não pode ser preenchido com base somente na média de renda municipal ou no total de domicílios. Faltam distribuição de renda familiar compatível, preços/faixas de financiamento de cada produto e coordenadas validadas.
- O gráfico de barras por renda/idade continua mostrando as categorias agregadas da LCM, sem série regional equivalente; o confronto municipal é apresentado em módulo separado com sua limitação.
- A visualização da malha municipal depende da disponibilidade da API de Malhas do IBGE e de política CORS no navegador; quando indisponível, permanece sem polígono, sem inventar localização.

## Próxima etapa
1. Homologar centro de cada terreno com evidência de mapa/croqui independente, data e revisor.
2. Publicar `data/ibge-project-context.json` e os GeoJSON de setores específicos utilizando o pipeline V8 existente.
3. Incluir distribuição verificável de renda **familiar** em unidades compatíveis, vincular preço/financiamento por empreendimento e só então calcular compradores elegíveis. Separar elegibilidade de interesse real de compra.

## Fonte oficial de rendimento
https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios_Rendimento_do_Responsavel/Agregados_por_municipios_renda_responsavel_BR_20260508_csv.zip
