"""Metadados das entradas do funil usando somente dados fictícios."""
import contextlib
import datetime as dt
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import marketing_cv_funnel as funnel


class FixedDate(dt.date):
    @classmethod
    def today(cls):
        return cls(2026, 11, 13)


class EntryClassificationTests(unittest.TestCase):
    def collect(self):
        project, other = funnel.PROJECTS[:2]
        leads = [
            {"idlead": 1, "nome": "Cliente fictício novo com retorno",
             "data_cad": "2026-01-10", "origem": "Facebook",
             "midia_original": "Whatsapp Facebook",
             "empreendimento_primeiro": project, "idempreendimento_primeiro": 10,
             "empreendimento_ultimo": other, "idempreendimento_ultimo": 20},
            {"idlead": 2, "nome": "Cliente fictício antigo",
             "data_cad": "2025-12-15", "origem": "Google",
             "midia_original": "Whatsapp Facebook",
             "empreendimento_primeiro": project, "idempreendimento_primeiro": 10},
            {"idlead": 3, "nome": "Cliente fictício outra origem",
             "data_cad": "2026-02-10", "origem": "Indicação",
             "empreendimento_primeiro": project, "idempreendimento_primeiro": 10},
            {"idlead": 4, "nome": "Cliente fictício novo sem retorno",
             "data_cad": "2026-03-10", "origem": "Google",
             "empreendimento_primeiro": project, "idempreendimento_primeiro": 10},
            {"idlead": 5, "nome": "Cliente fictício cadastro conflitante",
             "data_cad": "2026-01-01", "origem": "Facebook",
             "empreendimento_primeiro": project, "idempreendimento_primeiro": 10},
            {"idlead": 5, "nome": "Cliente fictício cadastro conflitante",
             "data_cad": "2026-01-02", "origem": "Facebook",
             "empreendimento_primeiro": project, "idempreendimento_primeiro": 10},
        ]
        conversions = [
            {"idlead": lead, "idlead_conversao": event, "referencia_data": day,
             "empreendimentos_conversao": [pid], "origem": "Facebook"}
            for lead, event, day, pid in [
                (1, 101, "2026-09-05", 10), (1, 102, "2026-09-12", 10),
                (1, 103, "2026-09-18", 20), (2, 104, "2026-09-07", 10),
                (3, 105, "2026-09-09", 10), (5, 106, "2026-09-10", 10),
            ]
        ]
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with patch.object(funnel, "credentials", return_value=("base", "email", "token")), \
                     patch.object(funnel.dt, "date", FixedDate), \
                     patch.object(funnel, "get", return_value={"dados": []}), \
                     patch.object(funnel, "read_complete", side_effect=[leads, conversions]), \
                     patch.object(funnel, "paged", side_effect=[[], [], [], []]), \
                     patch.dict(os.environ, {"CV_AUDIT_PRIVATE_PATH": ""}), \
                     contextlib.redirect_stdout(io.StringIO()):
                    funnel.main()
                return json.loads(Path("data/cv-funnel.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(previous)

    def test_new_registration_and_later_returns_keep_one_group(self):
        report = self.collect()
        group = next(g for g in report["prospects"] if len(g["entries"]) == 3)
        self.assertEqual(group["new_date"], "2026-01-10")
        self.assertEqual([e["date"] for e in group["entries"]],
                         ["2026-01-10", "2026-09-05", "2026-09-12"])
        self.assertEqual(report["classification_version"], 1)
        self.assertEqual(len(report["prospects"]), 5)

    def test_old_registration_return_has_no_eligible_new_date(self):
        report = self.collect()
        group = next(g for g in report["prospects"] if g["entries"][0]["date"] == "2026-09-07")
        self.assertIsNone(group["new_date"])
        self.assertTrue(group["whatsapp_acquisition"])

    def test_same_client_in_other_project_is_return_only_there(self):
        report = self.collect()
        other = [g for g in report["prospects"] if g["project"] == funnel.PROJECTS[1]]
        self.assertEqual(len(other), 1)
        self.assertIsNone(other[0]["new_date"])
        self.assertTrue(other[0]["whatsapp_acquisition"])
        self.assertEqual(other[0]["entries"], [{"date": "2026-09-18", "stage": 0}])

    def test_ineligible_original_channel_does_not_become_a_new_registration(self):
        report = self.collect()
        group = next(g for g in report["prospects"] if g["entries"][0]["date"] == "2026-09-09")
        self.assertIsNone(group["new_date"])
        self.assertFalse(group["whatsapp_acquisition"])
        self.assertNotIn("2026-02-10", [e["date"] for e in group["entries"]])
        # Cadastro conflitante não é incluído pelo novo metadado nem pelo retorno.
        self.assertFalse(any(e["date"] == "2026-09-10" for g in report["prospects"] for e in g["entries"]))

    def test_window_partition_uses_original_date_not_first_return(self):
        report = self.collect()
        def classify(since, until):
            selected = [g for g in report["prospects"] if any(since <= e["date"] <= until for e in g["entries"])]
            new = [g for g in selected if g["new_date"] is not None and since <= g["new_date"] <= until]
            returned = [g for g in selected if g not in new]
            return len(new), len(returned), len(selected)
        self.assertEqual(classify("2026-01-01", "2026-11-13"), (2, 3, 5))
        self.assertEqual(classify("2026-09-01", "2026-09-30"), (0, 4, 4))
        self.assertEqual(classify("2026-01-01", "2026-01-31"), (1, 0, 1))

    def test_projection_preserves_stages_and_has_no_individual_identifiers(self):
        first, returned = dt.date(2026, 1, 10), dt.date(2026, 9, 5)
        key = (funnel.PROJECTS[0], "private-test-id")
        result = funnel.public_prospects({key: {returned, first}},
            {"private-test-id": [(dt.date(2026, 2, 1), 4), (dt.date(2026, 10, 1), 2)]},
            {key: first}, {"private-test-id": True})
        self.assertEqual(result[0]["entries"], [
            {"date": "2026-01-10", "stage": 4}, {"date": "2026-09-05", "stage": 2}])
        self.assertEqual(set(result[0]), {"project", "new_date", "whatsapp_acquisition", "entries"})
        self.assertTrue(result[0]["whatsapp_acquisition"])
        self.assertNotIn("private-test-id", json.dumps(result))
        self.assertNotIn("Cliente fictício", json.dumps(self.collect()))
        with self.assertRaisesRegex(RuntimeError, "entrada correspondente"):
            funnel.public_prospects({key: {returned}}, {}, {key: first}, {"private-test-id": True})
        with self.assertRaisesRegex(RuntimeError, "não classificada"):
            funnel.public_prospects({key: {returned}}, {}, {}, {})


if __name__ == "__main__":
    unittest.main()
