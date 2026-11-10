# Coletor Meta Ads — LCM (fase de validação)

Este coletor **não** modifica anúncios, não acessa dados individuais de leads e **não publica** dados no GitHub Pages. Usa apenas GET na Meta Marketing API e requer `ads_read`.

## Preparação

1. Em GitHub → repositório → Settings → Secrets and variables → Actions → **Secrets**, crie `META_ACCESS_TOKEN` e cole **somente ali** o token do usuário de sistema Dashboard. Nunca compartilhe o valor em chat, commit ou print.
2. Opcional: em **Variables**, crie `META_AD_ACCOUNT_IDS` com os **IDs reais das contas de anúncios** separados por vírgulas (não o ID do portfólio empresarial). Sem essa variável, o coletor tenta listar contas por `/me/adaccounts`; alguns tokens de usuário de sistema podem não retornar essa lista.
3. Acesse Actions → **Meta Ads - Teste de leitura seguro** → Run workflow. Não marque opções de logging de debug com segredos.
4. Confira no log somente quantidade de contas, quantidade de linhas e erros genéricos. Nenhum token ou resultado de campanha é impresso.
5. Após validação, crie armazenamento privado para dados de campanha, controle de acesso ao painel e só então adicione sincronização automatizada e integração CV CRM.

## Rodar localmente (PowerShell Windows)

```powershell
$env:META_ACCESS_TOKEN = Read-Host "Cole seu token localmente (não compartilhe)"
$env:META_AD_ACCOUNT_IDS = "ID_CONTA_1,ID_CONTA_2"
python scripts/meta_ads_collector.py --days 7
Remove-Item Env:META_ACCESS_TOKEN
```

O exemplo de variável de IDs deve ser substituído pelos números reais antes de executar.

## Atenção à segurança

- O repositório GitHub Pages é público e o atual `index.html` contém dados comerciais individualizados. Revisar/remover esses dados **e o histórico de commits** antes de ampliar a exposição.
- Não criar workflows que façam commit automático de relatórios brutos; não usar token Meta no JavaScript.
- Totais da Meta e vendas do CV CRM não são diretamente atribuíveis até que IDs/UTMs sejam validados.
- `spend` usa a moeda configurada em cada conta. Consolidar somente depois de conferir moedas e fusos.
