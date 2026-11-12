# Histórico acumulado desde janeiro de 2026

As quatro coletas de Marketing começam em 2026-01-01 e terminam na data da
coleta. O calendário usa a cobertura comum realmente publicada, sem limite
artificial de 90 dias. O botão Ano de 2026 aplica janeiro até a última data
disponível daquele ano. Fontes ainda antigas mantêm a seleção restrita à sua
cobertura e exibem a sincronização pendente, sem inventar dias sem coleta.

## Contagens e retornos

O funil schema2 publica prospects anônimos agrupados: projeto e todas as
entradas elegíveis, cada uma com a etapa máxima alcançada após aquela entrada.
Não publica nomes nem identificadores nesse arquivo. O filtro escolhe a primeira
entrada de cada grupo dentro da seleção e conta esse grupo uma única vez.
Cadastro em janeiro + retorno em setembro conta uma pessoa no ano e uma em setembro.

As conversões schema4 mantêm séries diárias e grupos de eventos sem IDs.
A união entre datas e empreendimentos conta o lead uma vez em Todos; a seleção
individual mantém apenas os eventos daquele projeto. A classificação de retorno
e WhatsApp mantém as regras anteriores. Os formatos antigos continuam legíveis
durante a primeira atualização.

A auditoria pública tem uma linha por cliente/empreendimento, com entry_dates
para escolher a Data da Entrada dentro da seleção. Homônimos não são unidos por
nome. Os únicos campos adicionais publicados são as datas elegíveis; IDs,
documentos e contatos continuam descartados na projeção.

## Operação

A primeira execução reconsulta o período anual inteiro nas APIs. A atualização
diária também reprocessa o histórico desde janeiro para refletir alterações
retroativas; não há implementação de cursor incremental nesta versão.
O formato compacto evita gerar todas as combinações entre datas e reduz o
crescimento dos arquivos. A publicação recompõe apenas os JSONs gerados sobre
a main mais recente, usando push normal.

Execuções antigas do mesmo coletor são substituídas quando o código de coleta
muda. Alterações apenas de HTML não reiniciam a coleta do funil.
O investimento e as campanhas mantêm a leitura de campanhas atualmente ativas;
não representam automaticamente todo o investimento de campanhas já encerradas.

