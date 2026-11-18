# Executivo Comercial LCM

Painel executivo comercial da LCM. Reúne leads, funil de vendas, marketing
(Meta Ads), perfil e mapa de compradores e contexto geográfico do IBGE, a partir
dos dados do CV CRM.

O projeto tem três partes:

- **Páginas e módulos de frontend** (HTML, JS e CSS), servidos como site estático.
- **Servidor FastAPI** (`server.py`), hospedado no Render, com login para as rotas privadas.
- **Rotinas automáticas** (GitHub Actions + scripts Python) que coletam os dados
  e publicam arquivos JSON em `data/`.

## Aviso sobre dados

Este repositório é **público**. Os arquivos em `data/` são publicados de forma
automática e podem conter nomes reduzidos de leads e clientes, além de situação
comercial. Esses dados não devem ser tratados como anônimos. Contatos, CPF,
telefone, e-mail e IDs internos não devem ser gravados no repositório. Os detalhes
estão em [`docs/GESTAO_LEADS.md`](docs/GESTAO_LEADS.md) e
[`docs/AUDITORIA_COM_SENHA.md`](docs/AUDITORIA_COM_SENHA.md).

Credenciais ficam somente em variáveis de ambiente do Render e em GitHub Secrets.
Nunca as inclua em código, testes ou arquivos de dados.

## Estrutura

| Caminho | Conteúdo |
| --- | --- |
| `index.html`, `leads.html`, `marketing.html`, `perfil_compradores.html`, `leads-auditoria.html` | Páginas do painel |
| `lcm-*.js`, `lcm-*.css` | Módulos de interface (leads, funis, criativos, mapa de compradores, audiência) |
| `server.py`, `leads_operations.py` | Servidor FastAPI e coleta de leads |
| `scripts/` | Coletores e diagnósticos em Python (CV CRM, Meta Ads, IBGE, geocodificação) |
| `data/` | Arquivos JSON publicados pelas rotinas automáticas |
| `config/` | Configurações e listas de revisão (empreendimentos, endereços, IBGE) |
| `tests/` | Testes em Python e em Node |
| `docs/` | Documentação detalhada de cada módulo |
| `.github/workflows/` | Rotinas agendadas e validações |
| `render.yaml` | Configuração de deploy no Render |

## Executar localmente

```bash
pip install -r requirements.txt

export CVCRM_DOMINIO=...
export CVCRM_EMAIL=...
export CVCRM_TOKEN=...
export AUDIT_USER=...
export AUDIT_PASSWORD=...

uvicorn server:app --reload --port 8000
```

O endpoint `/api/health` indica se o servidor está no ar. Sem `AUDIT_USER` e
`AUDIT_PASSWORD`, as rotas privadas respondem com erro 503. As demais variáveis
estão listadas em `render.yaml`.

## Testes

```bash
python -m pytest tests                      # testes em Python
node tests/test_leads_management.cjs        # exemplo de teste em Node
```

Observações:

- `tests/test_leads_private_routes.py` precisa de `httpx`, além das dependências
  de `requirements.txt`.
- Os testes de contexto espacial do IBGE (`tests/test_ibge_spatial_context.py`)
  precisam de `geopandas`, que não está em `requirements.txt`.
- `tests/audience_v7_browser.cjs` e `tests/leads_funnels_browser.cjs` são testes de
  navegador.

## Atualizações automáticas

As coletas de Marketing rodam às 06h, 12h e 18h (horário de Brasília). Os
workflows agendados e o que cada um publica estão em
[`docs/AGENDAMENTO_ATUALIZACOES.md`](docs/AGENDAMENTO_ATUALIZACOES.md).

Cuidado ao fazer commits na `main`: muitos workflows disparam a cada push. Para
alterações que não precisam de coleta (como documentação), inclua `[skip ci]` na
mensagem do commit.

## Documentação

| Tema | Documento |
| --- | --- |
| Gestão de leads | [`GESTAO_LEADS.md`](docs/GESTAO_LEADS.md), [`GESTAO_LEADS_V1.md`](docs/GESTAO_LEADS_V1.md) |
| Auditoria de clientes | [`AUDITORIA_COM_SENHA.md`](docs/AUDITORIA_COM_SENHA.md) |
| Histórico anual | [`HISTORICO_ANUAL.md`](docs/HISTORICO_ANUAL.md) |
| Marketing e campanhas | [`MARKETING_AUTOMATICO_SEGURO.md`](docs/MARKETING_AUTOMATICO_SEGURO.md), [`CAMPANHAS_CRIATIVOS.md`](docs/CAMPANHAS_CRIATIVOS.md), [`META_ADS_INTEGRACAO.md`](docs/META_ADS_INTEGRACAO.md) |
| Agendamento | [`AGENDAMENTO_ATUALIZACOES.md`](docs/AGENDAMENTO_ATUALIZACOES.md) |
| Perfil e mapa de compradores | [`PUBLICO_COMPRADOR_V4.md`](docs/PUBLICO_COMPRADOR_V4.md), [`PUBLICO_COMPRADOR_V6_CORRECAO.md`](docs/PUBLICO_COMPRADOR_V6_CORRECAO.md), [`MAPA_COMPRADORES.md`](docs/MAPA_COMPRADORES.md), [`MAPA_INDIVIDUAL.md`](docs/MAPA_INDIVIDUAL.md), [`MAPA_POR_CEP.md`](docs/MAPA_POR_CEP.md) |
| IBGE e potencial por região | [`IBGE_DASHBOARD_V5.md`](docs/IBGE_DASHBOARD_V5.md), [`IBGE_ENDERECO_CVCRM.md`](docs/IBGE_ENDERECO_CVCRM.md), [`IBGE_GEOESPACIAL_V8_METODOLOGIA.md`](docs/IBGE_GEOESPACIAL_V8_METODOLOGIA.md), [`IBGE_V81_CORRECOES_E_LIMITES.md`](docs/IBGE_V81_CORRECOES_E_LIMITES.md), [`POTENCIAL_REGIAO_IBGE_V7.md`](docs/POTENCIAL_REGIAO_IBGE_V7.md) |
