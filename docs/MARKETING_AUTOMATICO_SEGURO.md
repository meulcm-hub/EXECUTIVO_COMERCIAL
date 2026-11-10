# Visão de Marketing LCM — atualização automática protegida

## Estado atual (10/11/2026)
- GitHub Pages: interface pública; **não** publicar dados comerciais sensíveis, tokens ou leads individuais.
- Meta Ads: 8 contas consultáveis com token `ads_read`.
- CV CRM CVDW: endpoint de leads acessível; não há atribuição de campanhas validada.
- GitHub Actions: consolidador programado diariamente às 11:15 UTC (08:15, horário de Brasília, quando UTC-3).
- A rotina **não publica** indicadores financeiros no site público. Não afirmar que o painel está em tempo real.

## Etapa seguinte: camada privada
Provisione um serviço com controle de acesso por usuário (ex.: Cloudflare Worker protegido pelo Cloudflare Access, com armazenamento privado e política de leitura somente para equipe LCM).

No GitHub, Configure **Secrets**:
- `MARKETING_INGEST_URL`: endpoint HTTPS para receber JSON agregado.
- `MARKETING_INGEST_TOKEN`: credencial independente, de ingestão (não é o token Meta nem o token CV).
- Segredos já existentes: `META_ACCESS_TOKEN`, `CVCRM_DOMINIO`, `CVCRM_EMAIL`, `CVCRM_TOKEN`.

O backend precisa:
1. autenticar o POST com token exclusivo; não imprimir o conteúdo;
2. limitar tamanho de payload, validar schema/contas/moedas/períodos;
3. armazenar JSON agregado criptografado e com retenção;
4. servir GET de métricas exclusivamente mediante login da equipe;
5. configurar CORS restrito se usado pelo navegador e impedir compartilhamento público;
6. fornecer logs de auditoria sem PII e permitir revogar acessos.

A rotina somente envia dados quando ambos os novos segredos estão configurados, quando não há falhas de contas, quando a moeda é conhecida e quando a consulta CV parece exaustiva dentro do limite. **Até lá não transmite nem persiste dados.**

## Alertas antes de publicar
- O repositório `EXECUTIVO_COMERCIAL` está público e o `index.html` contém nomes e detalhes de compradores. Esses dados **e o histórico Git** devem passar por revisão/remoção. Não considerar a interface atual protegida.
- Leads com origem Facebook/Instagram não são automaticamente leads pagos da Meta. Falta ligação comprovada por ID do anúncio/formulário e campanha.
- `CPL`, `CAC`, VGV atribuído e ROAS permanecem indisponíveis, não zero.
- A consulta CV pode ser parcial por limite de páginas; a paginação e o esquema devem ser auditados antes de uso executivo.
- O agendamento do GitHub Actions é de melhor esforço, não garante execução em horário exato.

## Como testar
Ações → `LCM - Consolidacao segura Meta e CV` → Executar fluxo de trabalho (30 dias, 10 páginas).
Verificar logs agregados. Não copiar tokens, payloads, URLs privadas ou informações pessoais em issues ou comentários.
