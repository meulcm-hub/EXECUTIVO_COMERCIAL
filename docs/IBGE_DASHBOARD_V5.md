# Público Comprador — IBGE V5 (dados municipais e análise do entorno)

## Correção de interface

Anteriormente, a aba "Potencial da Região" tentava carregar exclusivamente `data/ibge-project-context.json`. Como o arquivo ainda não existe, todos os empreendimentos exibiam a mesma mensagem genérica.

A partir da V5 a aba possui **três níveis distintos**:

1. **Endereço cadastral confirmado:** consulta `config/ibge-project-addresses.json`, com os 14 endereços fornecidos pelo responsável em 13/11/2026. Trata terrenos vizinhos (Flamboyant/Jatobá e Ipê/Jacarandá) como pontos a verificar separadamente. O endereço é apenas referência textual, não coordenada confirmada.
2. **Panorama municipal oficial:** busca o município e a UF na API de Localidades do IBGE e lê a tabela 4714, ano 2022, pela API de Agregados, usando as variáveis **93 (população residente)**, **6318 (área territorial)** e **614 (densidade demográfica)**. Mostra explicitamente "município inteiro" para evitar falsa atribuição dos valores a raio de 1, 3, 5 ou 10 km.
3. **Entorno geográfico por raio:** continua sendo carregado exclusivamente de `data/ibge-project-context.json`, se existir e se houver geocodificação de precisão confirmada e análise setorial 2022. Não oferece valores substitutos ou fictícios.

## Status e limitações

- O endpoint do IBGE é consultado em tempo real pelo navegador. Em caso de erro da API, a aba exibe "Não foi possível consultar" sem inventar números.
- As chamadas de localidades e indicadores são armazenadas em cache durante a sessão.
- Se o usuário selecionar "Todos os empreendimentos", a aba solicita uma seleção específica, evitando somas equivocadas de municípios repetidos.
- Adicionados Terra Solis e Extrema Meu Lar ao filtro de empreendimentos, mesmo sem cobertura na fonte demográfica original; gráficos de perfil permanecem indisponíveis quando a fonte estiver vazia.
- A análise por setor censitário e raio ainda **não está calculada**. Para isso, devemos validar o ponto central de cada terreno e produzir o JSON com métodos e fontes documentados.
- "Domicílios" e "renda" não são inferidos da tabela 4714; dependem de tabelas e/ou bases setoriais específicas verificadas.

## Fontes

- IBGE, API Localidades: https://servicodados.ibge.gov.br/api/v1/localidades/municipios
- IBGE, API de Agregados: https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/variaveis/93%7C6318%7C614?localidades=N6%5B3106200%5D
- SIDRA, Censo 2022, tabela 4714: https://sidra.ibge.gov.br/tabela/4714
- Endereços informados para LCM: `config/ibge-project-addresses.json`
