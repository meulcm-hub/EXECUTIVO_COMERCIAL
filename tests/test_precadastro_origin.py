import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from precadastro_dashboard import folder_origin, project
from leads_operational_history import opaque


class TestOrigin(unittest.TestCase):
    def setUp(self):
        self.secret = 'fixture'
        self.index = {opaque(self.secret, 'lead', '101'): 'Facebook',
                      opaque(self.secret, 'lead', '102'): 'Google',
                      opaque(self.secret, 'lead', '103'): 'Facebook',
                      opaque(self.secret, 'lead', '104'): None}

    def lookup(self, row):
        return folder_origin(row, self.secret, self.index)

    def test_direct_id_and_associated(self):
        self.assertEqual(self.lookup({'idlead':101}), ('Facebook','identified'))
        self.assertEqual(self.lookup({'leads_associados':[{'idlead':102}]}), ('Google','identified'))

    def test_duplicates_and_conflicting_origins(self):
        self.assertEqual(self.lookup({'idlead':'101,103','leads_associados':[{'idlead':101}]}), ('Facebook','identified'))
        self.assertEqual(self.lookup({'idlead':'101,102'}), ('Origens múltiplas','multiple'))

    def test_missing(self):
        self.assertEqual(self.lookup({}), ('Origem não identificada','no_link'))
        self.assertEqual(self.lookup({'idlead':999}), ('Origem não identificada','unmatched'))
        self.assertEqual(self.lookup({'idlead':104}), ('Origem não identificada','matched_without_origin'))

    def test_one_folder_no_identifiers(self):
        rows = {'301':{'data_cad':'2026-11-01 12:00:00','idlead':'101,103','situacao':'Aprovado'}}
        output = project(rows, {}, self.secret, dt.datetime(2026,11,2), self.index)
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]['origin'],'Facebook')
        self.assertNotIn('idlead',json.dumps(output))
        self.assertNotIn('leads_associados',json.dumps(output))


if __name__ == '__main__':
    unittest.main()
