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

## Execução real da geocodificação — 13/11/2026

GitHub Actions: https://github.com/meulcm-hub/EXECUTIVO_COMERCIAL/actions/runs/43464918342

- Empreendimentos lidos da API CV CRM: **14**.
- **1 candidato de correspondência exata:** RESIDENCIAL MONTTEBELO. É candidato de geocodificação, **ainda não aprovado** para o JSON público IBGE.
- **2 ambíguos:** RESIDENCIAL TURQUESA PARQUE; RESIDENCIAL TERRA SOLIS.
- **2 incompletos:** Residencial FLAMBOYANT; RESIDENCIAL FLORRES DO CERRADO IPÊ.
- **9 sem correspondência exata:** RESIDENCIAL TERRA MATER; RESIDENCIAL SANTA CATARINA; RESIDENCIAL JATOBÁ; RESIDENCIAL VILLAGE LAGOAS; SPE ARRAIAL COSTA VERDE; SPE ARRAIAL COSTA VERDE CLUB; RESIDENCIAL GREEN PLAZA; RESIDENCIAL EXTREMA MEU LAR; RESIDENCIAL FLORES DO CERRADO JACARANDÁ.

O artefato privado `coordenadas-empreendimentos-para-revisao` tem retenção de 7 dias. Não contém logradouros, número nem dados pessoais. Coordenadas candidatas possuem `verified: false`; **não se publica análise por raio** até validar. A consulta foi executada em lote único com pausas e o gatilho de push foi removido.

## Endereços confirmados em 13/11/2026

Foram recebidos 14 endereços ou referências de localização do responsável pelo projeto e preservados em `config/ibge-project-addresses.json`. São dados de cadastro de empreendimentos (não endereços de clientes).

**Esclarecimento do responsável:** Flamboyant/Jatobá e Ipê/Jacarandá são terrenos **vizinhos e distintos** que usam o mesmo endereço de referência. A geocodificação pode evitar consultas duplicadas, mas **não pode atribuir automaticamente a mesma coordenada central a esses empreendimentos**. Para eles, é necessário identificar individualmente o centro de cada lote/terreno por meio de mapa, polígono ou ponto confirmado.

Também não há ponto exato para SPE Arraial Costa Verde e SPE Arraial Costa Verde Club, porque foram informadas apenas a localidade Arraial d'Ajuda e a cidade Porto Seguro. O número de Santa Catarina é uma faixa (`1310–1420`), não uma portaria definida. Os lotes de Ipê/Jacarandá podem ser localizados espacialmente com croqui ou geolocalização do lote, não por número predial inexistente.

O workflow `ibge-geocode-curated.yml` faz um lote controlado de geocodificação, com distinção explícita `adjacent_distinct_site_requires_own_point` para referências idênticas de terrenos vizinhos. Todos os pontos seguem não verificados e não alimentam indicadores censitários até validação independente.

## Teste com os 14 endereços fornecidos — 13/11/2026

Execução: https://github.com/meulcm-hub/EXECUTIVO_COMERCIAL/actions/runs/43468171080 (concluída com sucesso).
- 14 empreendimentos distintos; 8 endereços completos distintos geocodificados após deduplicar referências compartilhadas.
- 1 ponto candidato de precisão por número: **RESIDENCIAL TURQUESA PARQUE**, coordenada ainda **não verificada por pessoa ou fonte independente**.
- 8 empreendimentos com endereço consultado mas sem correspondência exata no serviço.
- 5 empreendimentos sem endereço de precisão suficiente para geocodificação por porta (entre eles os dois Arraial, Ipê e Jacarandá, além de Santa Catarina com faixa numérica).
- **Flamboyant e Jatobá são vizinhos distintos no mesmo endereço de referência**. O mesmo ocorre com **Ipê e Jacarandá**. Não devemos compartilhar uma coordenada única entre esses terrenos.

O resultado foi armazenado no artefato de revisão `ibge-coordenadas-fornecidas-para-revisao` (retenção 7 dias). O workflow teve seu gatilho automático removido após a execução. Ainda não existem indicadores setoriais publicados nem coordenadas aprovadas no dashboard.
