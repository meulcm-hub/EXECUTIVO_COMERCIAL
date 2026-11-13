# Mapa público por CEP de origem

O mapa por CEP representa a área postal/rua de origem dos compradores, com uma cor por empreendimento. Não mostra a porta ou o número de uma residência. Compradores do mesmo empreendimento e CEP são agrupados em um ponto com a quantidade correspondente.

A coleta lê o CEP qualificado do cliente nas reservas do CV CRM. Só entram clientes/empreendimentos presentes na fonte do Perfil Público já existente. Repetições são removidas antes da contagem; CEPs conflitantes ficam pendentes. O geocodificador recebe somente CEPs, sem nomes ou identificadores de compradores.

A projeção pública permite apenas empreendimento, CEP, município/UF, coordenadas aproximadas, quantidade e precisão postal. Não contém nomes, IDs de clientes, documentos, rua, número ou endereço completo. Um ponto de CEP pode representar um ou mais compradores; todos ficam agrupados por CEP e empreendimento. A regra de cinco registros continua valendo para as visões anteriores de cidade e bairro.

As coordenadas aproximadas são consultadas na API CEP da AwesomeAPI e mantidas em cache geográfico. CEP sem coordenada válida não é deslocado para o centro municipal, nem recebe uma posição inventada. Fontes que devolvem o mesmo centro municipal para várias ruas não são utilizadas para produzir pontos postais.

A fonte `data/buyer-postal-locations.json` é separada das cidades/bairros da planilha. Quando há pontos postais válidos, a seleção inicial é CEP; Cidade e Bairro continuam disponíveis. O filtro de empreendimento é o mesmo do Perfil Público. Cada popup mostra o CEP, a cidade e a quantidade por empreendimento, sem características individuais.

O workflow de preparação tem somente acesso de leitura e disponibiliza apenas a projeção agregada e o cache geográfico para revisão. Não grava dados no repositório automaticamente. A publicação dos arquivos revisados utiliza a mesma branch/PR da implementação.
