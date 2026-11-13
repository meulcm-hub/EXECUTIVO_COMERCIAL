# Público Comprador — V6: correção da aba IBGE e filtros

## Sintoma reproduzido a partir das capturas
- A aba IBGE ainda mostrava a frase da versão anterior "Análise do entorno ainda não publicada..." sem o endereço do empreendimento, apesar de o JS V5 já estar na branch main.
- Etapa, Origem e Período apareciam bloqueados.

## Correção de carregamento
- Novo arquivo `lcm-audience-intelligence-v6.js` com novo nome e URL de recurso (não depende apenas de atualizar querystring de um arquivo em cache).
- Atualização de `index.html` para carregar o JS V6, e versão do CSS.
- Indicador visual `IBGE · V6` no cabeçalho do módulo para distinguir visualmente código antigo de código publicado.
- Abrir a página com querystring de cache nova e atualização completa para substituir página já carregada anteriormente.

## Filtros
A base de **vendas** possui `project`, `stage`, `agency`, `date` e `total`. Os filtros agora são:
- Empreendimento: repercute no perfil agregado, geografia do comprador, contexto IBGE e métricas de vendas.
- Etapa da venda: filtra apenas a base de vendas.
- Imobiliária (origem da venda): corresponde a `agency`, **não** à origem UTM/captação do lead, que não pode ser deduzida desse campo.
- Período da venda: ano da data da venda, filtra apenas a base de vendas.
Os três filtros de vendas afetam o ticket médio, a contagem de vendas no recorte e o ticket médio do comparativo de empreendimentos. Não afetam demografia ou IBGE, por ausência de ligação individual nas fontes disponíveis. Esse limite é comunicado ao usuário, e não se exibe falsa sincronização.

## IBGE
Apresenta endereço confirmado por empreendimento a partir de `config/ibge-project-addresses.json`. Faz consulta pela API do IBGE a população, área e densidade municipais (Censo 2022, tabela 4714). Os indicadores são municipais, não dos raios de 1, 3, 5 ou 10 km. Dados setoriais por raio somente quando `data/ibge-project-context.json` existir com coordenadas verificadas e método setorial validado.

## Validação
Verificar no navegador o marcador `IBGE · V6`, endereço do empreendimento e os três selects habilitados. Alterar etapa/ano/imobiliária e conferir mudança da contagem de vendas e do ticket, sem mudanças artificiais nos perfis ou no IBGE. Trocar de empreendimento e conferir endereço e município.
