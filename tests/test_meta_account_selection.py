import os
import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import meta_ads_collector as meta

class MetaAccountSelectionTests(unittest.TestCase):
    def test_larger_catalog_only_selects_eight_linked_accounts(self):
        expected=[{'id':'act_'+aid,'name':'Conta fictícia','currency':'BRL'} for aid in meta.DASHBOARD_ACCOUNT_IDS]
        catalog=expected+[{'id':'act_'+str(9000000+i),'currency':'BRL'} for i in range(16)]
        with patch.dict(os.environ,{'META_AD_ACCOUNT_IDS':''}),patch.object(meta,'request',return_value=catalog):
            self.assertEqual(meta.accounts(),expected)
    def test_missing_linked_account_blocks_incomplete_publication(self):
        catalog=[{'id':'act_'+aid,'currency':'BRL'} for aid in meta.DASHBOARD_ACCOUNT_IDS[:-1]]
        with patch.dict(os.environ,{'META_AD_ACCOUNT_IDS':''}),patch.object(meta,'request',return_value=catalog):
            with self.assertRaisesRegex(RuntimeError,'1 das 8'):meta.accounts()
    def test_explicit_ids_preserve_currency_and_deduplicate(self):
        item={'id':'act_123456','currency':'BRL','name':'Conta fictícia'}
        with patch.dict(os.environ,{'META_AD_ACCOUNT_IDS':'act_123456,123456'}),patch.object(meta,'request',return_value=[item]) as request:
            self.assertEqual(meta.accounts(),[item])
            request.assert_called_once_with('me/adaccounts',{'fields':'id,name,account_status,currency','limit':'100'})


    def test_account_missing_from_catalog_is_checked_directly(self):
        rows=[{'id':'act_'+aid,'currency':'BRL'} for aid in meta.DASHBOARD_ACCOUNT_IDS]
        with patch.dict(os.environ,{'META_AD_ACCOUNT_IDS':''}),patch.object(meta,'request',side_effect=[rows[:-1],rows[-1]]) as request:
            self.assertEqual(meta.accounts(),rows)
            self.assertEqual(request.call_count,2)
    def test_direct_api_metadata_object_is_preserved(self):
        import io,json
        item={'id':'act_123456','currency':'BRL','name':'Conta fictícia'}
        with patch.object(meta,'TOKEN','ficticio'),patch.object(meta.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(item).encode())):
            self.assertEqual(meta.request('act_123456',{'fields':'id,currency'}),item)

    def test_catalog_permission_denied_checks_all_linked_assets_directly(self):
        rows=[{'id':'act_'+aid,'currency':'BRL','name':'Conta fictícia'} for aid in meta.DASHBOARD_ACCOUNT_IDS]
        for code in (10,200):
            output=io.StringIO()
            denied=meta.MetaAPIError('mensagem confidencial não imprimir',code)
            with self.subTest(code=code),patch.dict(os.environ,{'META_AD_ACCOUNT_IDS':''}), \
                 patch.object(meta,'request',side_effect=[denied,*rows]) as request, \
                 contextlib.redirect_stdout(output):
                self.assertEqual(meta.accounts(),rows)
                self.assertEqual(request.call_count,9)
                self.assertEqual([call.args[0] for call in request.call_args_list[1:]],
                                 ['act_'+aid for aid in meta.DASHBOARD_ACCOUNT_IDS])
            self.assertIn('validando contas vinculadas diretamente',output.getvalue())
            self.assertNotIn('confidencial',output.getvalue())

    def test_catalog_expired_token_network_or_unclassified_error_never_falls_back(self):
        failures=[meta.MetaAPIError('token expirado',190),meta.MetaNetworkError('falha de rede'),
                  meta.MetaAPIError('parâmetro inválido',100),RuntimeError('erro não classificado')]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), \
                 patch.dict(os.environ,{'META_AD_ACCOUNT_IDS':''}), \
                 patch.object(meta,'request',side_effect=failure) as request:
                with self.assertRaises(RuntimeError) as result:meta.accounts()
                self.assertIs(result.exception,failure)
                self.assertEqual(request.call_count,1)

    def test_partial_direct_permissions_keep_required_accounts_and_clear_missing_name(self):
        rows=[{'id':'act_'+aid,'currency':'BRL'} for aid in meta.DASHBOARD_ACCOUNT_IDS[:-1]]
        with patch.dict(os.environ,{'META_AD_ACCOUNT_IDS':''}), \
             patch.object(meta,'request',side_effect=[meta.MetaAPIError('catálogo negado',200),*rows,
                                                      meta.MetaAPIError('não publicar mensagem bruta',200)]), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'1 das 8 contas vinculadas: LCM - Jatobá') as result:
                meta.accounts()
            self.assertNotIn('mensagem bruta',str(result.exception))

    def test_catalog_fallback_preserves_explicit_ids_and_currency(self):
        row={'id':'act_123456','name':'Conta fictícia','currency':'BRL'}
        with patch.dict(os.environ,{'META_AD_ACCOUNT_IDS':'act_123456,123456'}), \
             patch.object(meta,'request',side_effect=[meta.MetaAPIError('sem catálogo',10),row]) as request, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(meta.accounts(),[row])
            self.assertEqual(request.call_count,2)
            self.assertEqual(request.call_args.args[0],'act_123456')

    def test_direct_expired_token_or_network_failure_does_not_retry_all_accounts(self):
        for failure in [meta.MetaAPIError('token expirado',190),meta.MetaNetworkError('falha de rede')]:
            with self.subTest(failure=type(failure).__name__), \
                 patch.dict(os.environ,{'META_AD_ACCOUNT_IDS':''}), \
                 patch.object(meta,'request',side_effect=[meta.MetaAPIError('sem catálogo',200),failure]) as request, \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError) as result:meta.accounts()
                self.assertIs(result.exception,failure)
                self.assertEqual(request.call_count,2)
