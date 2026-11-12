import os
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
