# Mapa individual de compradores a partir das reservas

## Diferença para o mapa publicado

O mapa público mostra centros de cidades/bairros com contagens agregadas. Uma localização individual precisa do endereço residencial do comprador na reserva, nunca do endereço do empreendimento ou da unidade comprada.

## Consulta e geocodificação

1. Ler reservas autorizadas no CV CRM por uma API no servidor.
2. Vincular comprador e empreendimento por identificadores estáveis, sem publicar os identificadores.
3. Selecionar apenas endereço residencial explicitamente ligado ao comprador: logradouro, número, bairro, município, UF e CEP, quando disponíveis. Informações incompletas ou conflitantes ficam pendentes.
4. Resolver coordenadas com precisão declarada pelo geocodificador e guardar o cache em armazenamento privado. Resultado por CEP, bairro ou cidade não deve ser apresentado como porta do imóvel. Não inventar posições para separar compradores.
5. Entregar pontos somente a usuários autenticados e autorizados. Endereços e coordenadas não entram em JSON público, histórico Git, logs, artefatos públicos ou URLs de imagens estáticas.

## Visualização privada proposta

- Reutilizar o filtro de empreendimento do perfil.
- Agrupar marcadores no zoom distante e abrir pontos individuais ao aproximar.
- Cada popup mostra apenas o necessário ao usuário autorizado; não acrescentar nome ou endereço ao mapa público.
- Diferenciar endereço confirmado de localização aproximada e mostrar separadamente registros sem coordenadas.
- Manter os demais indicadores do painel públicos.

## Dependências para publicação

A página atual usa GitHub Pages, que serve arquivos públicos e não protege dados com uma senha em JavaScript. O mapa individual requer backend e armazenamento privados, além de autenticação e uma lista de usuários autorizados. A consulta de disponibilidade dos campos pode ser feita antes dessa configuração, sem salvar nem exibir endereços.
