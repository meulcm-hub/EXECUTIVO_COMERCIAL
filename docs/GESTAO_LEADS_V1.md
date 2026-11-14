# Gestão de Leads LCM — módulo isolado (V1)

## Arquitetura
- `leads.html` e `lcm-leads.css`: página independente, identidade escura.
- `lcm-leads.js`: filtros globais, coortes, indicadores, funil clicável, séries e exportação agregada.
- `lcm-shell.js`: uma entrada nova na navegação; não altera as demais páginas.
- Fonte **existente**, `data/cv-funnel.json`, sem cópia de registros individuais.

## Regras auditadas
- Fonte utilizada: CV CRM, `schema_version=2`, `validated=true`, `classification_version=1`, coortes por `prospect_date`.
- Seleção única por elemento de `prospects` e empreendimento, a partir da primeira entrada de cada grupo dentro do período selecionado. Entradas adicionais do mesmo grupo dentro do intervalo não aumentam o total.
- Novo: `new_date` original dentro da janela. Retorno: grupo com entrada elegível sem `new_date` nessa janela.
- Funil: `stage` cumulativo 0..4 publicado pela coleta; etapa filtrada inclui todos que atingiram ao menos o estágio selecionado.
- Vendas: apenas quando `sales_link_validated===true`. **Não** são inferidas de reservas.
- Mudança percentual de leads: apenas quando há intervalo anterior com cobertura igual à janela atual.
- WhatsApp: `whatsapp_acquisition` do grupo. **Não** demonstra vínculo à campanha nem à Meta Lead Ads.
- Agrupamento temporal: primeira entrada elegível por grupo no recorte; diária, semanal (segunda-feira) ou mensal.
- Taxa de conversão: vendas vinculadas / grupos na coorte, quando venda validada. Não é taxa de todas as entradas históricas do CV.
- Exportação: CSV agregado por empreendimento; não contém PII.

## Limitações e riscos atuais
**Esta V1 ainda não satisfaz o módulo completo.** A fonte é de quatro empreendimentos e do funil histórico com regras antigas (Facebook/Google), não 100% da base de leads CV CRM. Não permite afirmar que a entrada é exclusivamente FB ou GE com mídia WhatsApp Facebook. Uma pessoa pode aparecer em mais de um empreendimento; a deduplicação global por CPF/telefone seria indevida sem identificador/consentimento e tratamento adequado.

Não existem no JSON: ID de lead, SDR, corretor, status atual, situação detalhada, nome, telefone, criação com horário, primeiro atendimento, última interação, atribuição ao responsável, negociação, etapas reais de atendimento/distribuição, pendências e SLA. Não são mostrados números fictícios. O mapa de etapas (prospect, agendamento, visita, análise, venda) reflete a **coorte publicada**, não substitui verificação de todos os estados do CV CRM.

Em produção, qualquer carteira individual, dados pessoais e histórico de atendimento precisa de backend autenticado e autorização por função. **Não publicar nomes/telefones em JSON do GitHub Pages**.

## Próxima etapa
1. Levantar endpoints disponíveis para usuários, responsáveis, distribuição, interações, tarefas, ocorrências, reservas, pré-cadastro e vendas.
2. Construir backend privado com paginação e deduplicação por `idlead`, coleta incremental, histórico de alterações e datas UTC/Brasília.
3. Definir identidade dos SDRs e sua atribuição por lead no momento de entrada; separar histórico de responsáveis do responsável atual.
4. Homologar SLA e regras de etapas/situações com o negócio.
5. Gerar KPIs operacionais e tabela autenticada de clientes, mantendo esta página pública somente com agregados autorizados.

## Testes
```bash
node --check lcm-leads.js
node --check lcm-shell.js
python -m unittest discover -s tests -p test_leads_dashboard_contract.py
```

## Taxonomia de oportunidades solicitada — 13/11/2026

**Funil atual: 6 grupos**
1. PROSPECÇÃO: PROSPECÇÃO, NOVO LEAD
2. ATENDIMENTO: CONTATO, CAD/C 1, 2, 3, 4, 5, 6, 7
3. AGENDAMENTO: AGENDAMENTO, CAD/A 1, 3, 7, 14, 20
4. VISITA: VISITA
5. ANÁLISE DE CRÉDITO: ANÁLISE DE CRÉDITO
6. VENDA: VENDA REALIZADA

**Funil acumulado: sequência literal de 16 etapas**
PROSPECÇÃO → CONTATO → CAD/C 1 → CAD/C 2 → CAD/C 4 → CAD/C 5 → CAD/C 7 → AGENDAMENTO → CAD/A 1 → CAD/A 3 → CAD/A 7 → CAD/A 14 → CAD/A 20 → VISITA → ANÁLISE DE CRÉDITO → VENDA REALIZADA.

A sequência omite CAD/C 3 e CAD/C 6 deliberadamente, conforme solicitação. No funil atual esses estados são agrupados em ATENDIMENTO, como requerido por "CAD/C 1 até 7".

O agrupamento e a nomenclatura estão em `lcm-leads-stage-config.js`. Os dois painéis estão na seção `#funil` da página `leads.html`.

**Diferença de medida:** o funil por oportunidade exige o estado atual de cada lead, deduplicado por projeto+ID. O funil acumulado exige o conjunto real de movimentações históricas desse lead por etapa. Etapas puladas ou sem eventos não devem ser preenchidas por inferência; não necessariamente existe trajetória linear obrigatória em todos os casos.

**Disponibilidade atual:** `data/cv-funnel.json` possui apenas cinco marcos de coorte: prospect, agendamento, visita, análise e venda. Portanto, são exibidos contadores históricos comprovados para os quatro últimos no funil acumulado, com ressalva de cobertura parcial. Os demais níveis detalhados e o funil de **situação atual** permanecem sem contagem até um extrato de oportunidades (todas as origens, estados atuais, IDs e movimentações) ser validado. O filtro "Etapa validada da coorte" permanece ligado à base histórica, não à nova taxonomia completa.

**Proteção:** o extrato operacional com IDs e histórico de situações deverá ser processado no runner privado; somente agregados não identificáveis poderão ser publicados no GitHub Pages. O módulo não foi integrado a um backend autenticado para carteira individual.

Teste: `node --test tests/test_leads_stage_classification.cjs`.

## Coleta integral desde o primeiro lead — 13/11/2026

Novo coletor **independente do Marketing**: `scripts/leads_full_history.py`.
Consulta `GET /api/v1/cvdw/leads` **sem data inicial, sem origem, sem situação e sem empreendimento**. Percorre todas as páginas declaradas pela API e falha se faltarem páginas ou registros sem ID/data válidos. Escolhe o snapshot mais recente por `idlead` e preserva a data de cadastro original `data_cad` (não substitui pela `referencia_data` de alteração). A data inicial oficial publicada é o menor `data_cad` real, nunca 2026-01-01 presumido.

Arquivo público esperado após coleta e auditoria: `data/leads-all-summary.json`. Nunca contém nomes, telefones, CPF ou IDs individuais. Só agregados para o dashboard. Leads sem projeto são `SEM EMPREENDIMENTO`.

A primeira execução integral pode ser longa e depende da disponibilidade da API, permissões, do limite de paginação e dos GitHub Actions. **Sem confirmação da execução e da cobertura, não anunciar total completo**. O GitHub Pages exibirá pendência caso o arquivo não esteja validado.

Workflow: `.github/workflows/leads-full-history.yml`. Executa três vezes por dia e por despacho manual e alteração do coletor. Testes em `tests/test_leads_full_history.py`.

A base histórica completa não substitui o histórico de movimentações e não permite inferir etapa, SLA ou venda a partir de situação textual isolada; por enquanto a página mantém o funil de Marketing em seção identificada como fonte parcial. Dados individuais deverão ser consultados em ambiente com acesso controlado. Mesmo dois nomes são dados pessoais e não devem ser publicados em Pages sem proteção.

## Filtros múltiplos da Gestão de Leads — 14/11/2026

- **Origem**: todas as origens distintas retornadas pela fonte integral CV CRM, sem lista fixa de Marketing; é permitido marcar várias ao mesmo tempo.
- **Mídia de Visita**: somente campos explicitamente relacionados a visita (`midia_visita`, `midia_visita_nome`, `midia_da_visita`, `midiaVisita`, `midia_visita_original`). Não substituir por `midia_original` ou `midia_ultimo`, que representam outros conceitos.
- Campo explicitamente vazio: `NÃO INFORMADA`. Campo não exposto pela API: `NÃO DISPONÍVEL NA API`.
- Sem opções marcadas = todas. Com opções selecionadas, vale **OU dentro de cada filtro** e **E entre origem, mídia de visita, empreendimento e período**. O botão Limpar redefine tudo.
- O arquivo agregado passou para `schema_version=2` com a dimensão `visit_media`. Até nova coleta integral bem-sucedida, o filtro não inventa opções nem exibe resultados falsos.
- Quando os filtros de origem/mídia estão ativos, os painéis da coorte parcial de Marketing são ocultados, pois não possuem essas dimensões e não podem ser recalculados com fidelidade. Marketing permanece inalterado.
- A mídia de visita exige confirmação do campo real na resposta da API. O coletor não afirma cobertura sem evidência; caso não exista, o valor `NÃO DISPONÍVEL NA API` explicita a limitação.
