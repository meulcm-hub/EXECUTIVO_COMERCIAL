# Integração IBGE pelo endereço do empreendimento — CV CRM

## Regra aprovada
O centro dos raios de 1, 3, 5 e 10 km deve ser o endereço **do empreendimento**, cadastrado no CV CRM. Não utilizar o município de maior frequência dos compradores, nem o centro municipal ou bairro como substituto.

## Pipeline
1. Consultar somente o endpoint cadastral de empreendimentos do CV CRM com as credenciais existentes em GitHub Actions. Não consultar campos de clientes. O script `scripts/cvcrm_project_address_audit.py` faz uma auditoria inicial **somente por contagens de campos**, sem armazenar endereços.
2. Confirmar no retorno do ambiente da LCM os campos de logradouro, número, cidade, UF, CEP e identificador do empreendimento. O endpoint inicialmente configurado é `GET /api/v1/cadastros/empreendimentos`, e sua disponibilidade/permissões na conta LCM devem ser verificadas. No caso de HTTP 403/404, **não** testar endpoints de pessoas como alternativa.
3. Em pipeline de processamento privado, geocodificar o endereço completo, confirmar correspondência de **número e logradouro**, município e UF. Rejeitar resultados municipais, CEP sem número e endereços ambíguos. Coordenadas publicadas apenas após revisão/validação.
4. Baixar dados oficiais do Censo 2022 (agregados e malhas dos setores, incluindo retificações publicadas em 2026), relacionar espacialmente cada círculo com a malha. Para estimativas aproximadas ponderar por fração de área intersectada e deixar clara a limitação de uniformidade.
5. Publicar somente um JSON agregado `data/ibge-project-context.json`, sem dados pessoais. A tela usa esse JSON como **fonte exclusiva** para métricas de raio. Se o JSON não existir ou faltar validação, exibe uma pendência — sem números inventados.

## Contrato público de dados
```json
{
  "schema_version": 1,
  "projects": [
    {
      "project": "nome normalizado conforme filtro do dashboard",
      "center": {
        "source": "CV CRM",
        "verified": true,
        "precision": "address_number",
        "lat": -19.0,
        "lng": -44.0
      },
      "radii": {
        "3": {
          "year": 2022,
          "method": "sector_intersection_area_weighted",
          "population": 0,
          "households": 0,
          "populationDensity": 0
        }
      }
    }
  ]
}
```
**Os números e coordenadas acima são apenas exemplo de contrato**, não correspondem a um empreendimento real e **não devem ser publicados como dados**.

## Dados disponíveis e pendentes
- Contagens de população e domicílios por setor: IBGE Censo 2022; arquivos corrigidos em outubro de 2026.
- Renda domiciliar/responsável pelo domicílio: coleção setorial específica, com dicionário de variáveis e período; não combinar indevidamente renda por pessoa com renda familiar.
- Faixa etária e perfil socioeconômico: somente quando os indicadores estiverem disponíveis na mesma escala e não exigirem inferências proibidas.
- Distância da origem do comprador ao empreendimento: depende do mapa postal validado do comprador e do centro validado do empreendimento, com precisão explicitada.

## Execução e segurança
- A auditoria pode ser iniciada no GitHub Actions, workflow **LCM - Validar endereços de empreendimentos para IBGE**.
- Ela exige os secrets já existentes `CVCRM_DOMINIO`, `CVCRM_EMAIL`, `CVCRM_TOKEN`.
- Não versionar dump da API, logradouro, números, dados pessoais, resposta bruta nem token.
- Falha do serviço ou ausência de coordenadas validadas deve resultar em **sem dados**, nunca coordenadas supostas.

Fontes:
- https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html?edicao=41852&t=downloads
- https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais/2971-np-malhas-de-setores-censitarios-divisoes-intramunicipais/26565-malhas-de-setores-censitarios-divisoes-intramunicipais.html
- https://desenvolvedor.cvcrm.com.br
