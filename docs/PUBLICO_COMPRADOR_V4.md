# Público Comprador — Inteligência Comercial V4

## Objetivo
Reestruturação funcional e visual baseada na referência do dashboard compacto: fundo azul-marinho, cards discretos, verde, roscas para gênero e estado civil, barras de perfil, mapa e insights.

## Fontes e métodos
- Perfil demográfico: agregado `D.audience` já incorporado em `index.html`. Não contém o relacionamento individual entre cliente, empreendimento, origem de captação, etapa e data.
- Ticket médio de vendas: média aritmética de `SALES[].total` para o empreendimento selecionado; não é automaticamente o ticket dos mesmos compradores que responderam ao perfil.
- Gênero, idade, renda, estado civil, cidade, bairro e profissão: denominador próprio por categoria (registros classificados), para evitar percentuais acima de 100%.
- Mapa: `lcm-buyer-map.js` e `buyer-locations.json` agregados; CEP depende do fluxo dedicado de revisão de coordenadas. Localizações não identificam residências.
- IBGE (Censo 2022): API oficial de Localidades e API de Agregados, tabela 4714 (população, área, densidade), com consulta municipal por nome único e código IBGE. Dados do município não equivalem a um raio de entorno.
- Dados setoriais e indicadores de domicílios, rendimentos e distribuição etária: **pendentes** de pipeline setorial e da coordenada exata do empreendimento. Referência oficial: https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html?edicao=41852&t=downloads

## Limites explicitados na interface
- Total único de compradores: não pode ser inferido da soma de categorias (por exemplo, em Jacarandá existem 23 registros de gênero e apenas 17 de faixa etária). O KPI informa especificamente compradores **com gênero informado**.
- Conversão de leads em vendas: não disponibilizada sem vínculo auditado dos IDs e mesmo período de elegibilidade.
- Tempo médio de compra: não disponibilizado sem data de entrada e data de venda por cliente.
- Filtros Etapa, Origem e Período: desativados até existir fonte unificada e auditada. São mostrados para não sugerir falsa sincronização entre dados incompatíveis.
- Comparativo: apresenta apenas dimensões com dados agregados existentes; conversão não é estimada.

## Testes de aceitação recomendados
1. Selecionar Jacarandá, observar cobertura de gênero 23 e faixa etária 17 e nenhum percentual >100%.
2. Alternar Visão Geral, Perfil, Origem, IBGE, Comparativo e voltar: filtros e mapa não devem perder estado.
3. Selecionar Village Lagoas e retornar a Jacarandá: todas as categorias e o mapa devem refletir o empreendimento.
4. Abrir em 1440px, 1024px e dispositivo móvel; conferir roscas, barras, cards e ausência de scroll horizontal.
5. Verificar console de navegador, requests para IBGE e carregamento do mapa.
6. Validar visualmente impressão/PDF.

## Próxima integração de dados
Construir uma fonte privada por comprador/empreendimento com IDs cruzados e datas, derivar exclusivamente uma projeção estatística segura para o front-end; nunca publicar endereços e identificadores pessoais em GitHub Pages.
