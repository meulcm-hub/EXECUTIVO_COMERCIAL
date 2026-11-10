import sys
import unittest
sys.path.insert(0, "scripts")
from marketing_consolidate import classify_channel, guess_channel

class ChannelRules(unittest.TestCase):
    def test_shared_search_is_meta(self):
        row={"origem_nome":"Busca Compartilhada"}
        self.assertEqual(classify_channel(row),"meta_busca_compartilhada_cv")
        self.assertEqual(guess_channel(row),"meta_declarada")
    def test_whatsapp_facebook(self):
        row={"origem":"Busca Compartilhada","midia_original":"Whatsapp Facebook"}
        self.assertEqual(classify_channel(row),"meta_whatsapp_cv")
        self.assertEqual(guess_channel(row),"meta_declarada")
    def test_standard_meta(self):
        self.assertEqual(classify_channel({"origem_nome":"Facebook"}),"meta_outros_cv")
    def test_google_stays_google(self):
        self.assertEqual(guess_channel({"origem_nome":"Google"}),"google_declarada")
    def test_prevent_double_count(self):
        row={"origem_nome":"Busca Compartilhada","midia_original":"Whatsapp Facebook"}
        subtype=classify_channel(row)
        self.assertEqual(subtype,"meta_whatsapp_cv")
        self.assertNotEqual(subtype,"meta_busca_compartilhada_cv")

if __name__=="__main__":
    unittest.main()
