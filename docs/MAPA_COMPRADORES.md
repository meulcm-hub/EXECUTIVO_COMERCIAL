# Mapa do Público Comprador

O mapa usa a aba **Perfil Público - Fonte** da base já existente. Cidade e
bairro são lidos juntos; a contagem remove repetições por cliente/empreendimento.
Conflitos de cidade não recebem uma localização escolhida arbitrariamente.

O JSON público contém apenas empreendimento, localidade, UF, coordenadas do
centro da cidade ou bairro e contagem. Somente grupos com pelo menos cinco
clientes são publicados. Não contém identificadores, nomes ou endereços.

Cidades são identificadas por correspondência exata com nome único no Brasil,
na base de municípios. Homônimos sem UF ficam pendentes. Bairros precisam de
correspondência confirmada de nome, município, UF e país; uma coordenada
municipal nunca é apresentada como se fosse um bairro.

As coordenadas municipais vêm de [Municípios Brasileiros](https://github.com/kelvins/municipios-brasileiros),
licença MIT, Copyright (c) 2016 Kelvin S. do Prado. O cache de bairros utiliza
Nominatim/OpenStreetMap, ODbL. As buscas contêm somente nomes de localidades.

O script `scripts/buyer_locations.py` usa o cache por padrão. Uma consulta
geográfica adicional é opcional (`--geocode`), sequencial, com intervalo de
15,1 segundos, respeitando quatro consultas por minuto para rotinas recorrentes.
`--one-time` destina-se apenas a um lote manual único, com 1,1 segundo de intervalo.
O workflow apenas valida e gera um artefato de localidades para revisão; não altera a branch principal nem habilita geocodificação externa.

Leaflet 1.9.4 está incluído em `vendor/leaflet`, com sua licença. O fundo
satélite usa Esri World Imagery com atribuição; a opção Ruas usa OpenStreetMap.
O mapa acompanha o filtro de empreendimento existente e carrega somente ao
abrir Público Comprador. Os popups mostram quantidades por empreendimento;
não apresentam uma soma entre projetos como compradores únicos globais.

O mapa representa a base de localização da planilha, que pode ter uma versão
diferente do resumo incorporado do perfil. Localidades sem confirmação ou
grupos pequenos não aparecem. Ele não representa endereços individuais.
