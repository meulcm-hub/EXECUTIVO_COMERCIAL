"""Conciliação da auditoria com a safra usando apenas dados fictícios."""
import contextlib
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import marketing_cv_funnel as funnel


class AuditCohortTests(unittest.TestCase):
    def test_return_uses_cohort_date_and_lead_origin(self):
        today = dt.date.today()
        original_day = today - dt.timedelta(days=120)
        return_day = today - dt.timedelta(days=2)
        new_day = today - dt.timedelta(days=1)
        project = funnel.PROJECTS[0]
        leads = [
            {"idlead": 1, "nome": "Cliente fictício retorno",
             "data_cad": original_day.isoformat(),
             "empreendimento_primeiro": project, "idempreendimento_primeiro": 10,
             "origem": "Google", "situacao": "Em atendimento"},
            {"idlead": 2, "nome": "Cliente fictício novo",
             "data_cad": new_day.isoformat(),
             "empreendimento_primeiro": project, "idempreendimento_primeiro": 10,
             "origem": "Facebook", "situacao": "Novo"},
        ]
        conversions = [
            {"idlead": 1, "idlead_conversao": 101,
             "referencia_data": return_day.isoformat(),
             "empreendimentos_conversao": [10], "origem": "Facebook"},
            {"idlead": 1, "idlead_conversao": 102,
             "referencia_data": today.isoformat(),
             "empreendimentos_conversao": [10], "origem": "Facebook"},
        ]
        precad = [{"idlead": 1, "data_cad": new_day.isoformat(),
                   "situacao": {"nome": "Aprovado"}}]
        reservations = [{"idreserva": 20, "idlead": 1, "venda": "Sim",
                         "situacao": "Vendida", "data_venda": today.isoformat(),
                         "referencia_data": today.isoformat()}]
        previous_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            private_path = Path(directory) / "audit-private.json"
            try:
                os.chdir(directory)
                with patch.object(funnel, "credentials", return_value=("base", "email", "token")), \
                     patch.object(funnel, "get", return_value={"dados": []}), \
                     patch.object(funnel, "read_complete", side_effect=[leads, conversions]), \
                     patch.object(funnel, "paged", side_effect=[[], [], precad, reservations]), \
                     patch.dict(os.environ, {"CV_AUDIT_PRIVATE_PATH": str(private_path)}), \
                     contextlib.redirect_stdout(io.StringIO()):
                    funnel.main()
                private = json.loads(private_path.read_text(encoding="utf-8"))
                public = json.loads(Path("data/cv-funnel.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(len(private["rows"]), 2)  # Dois retornos não duplicam o lead.
        by_id = {row["idlead"]: row for row in private["rows"]}
        returned = by_id["1"]
        self.assertEqual(returned["origem"], "Google")  # Leads, não a conversão Facebook.
        self.assertEqual(returned["data_entrada"], original_day.isoformat())
        self.assertEqual(returned["entry_dates"], [original_day.isoformat(),return_day.isoformat(),today.isoformat()])
        self.assertEqual(returned["tipo_entrada"], "Novo cadastro")
        self.assertEqual(returned["situacao_lead"], "Em atendimento")
        self.assertEqual(returned["situacao_precadastro"], "Aprovado")
        self.assertEqual(returned["situacao_reserva"], "Vendida")
        self.assertEqual(returned["data_venda"], today.isoformat())
        self.assertEqual(by_id["2"]["data_entrada"], new_day.isoformat())
        self.assertEqual(by_id["2"]["tipo_entrada"], "Novo cadastro")
        self.assertEqual(by_id["2"]["data_venda"], "")

        self.assertEqual(public["schema_version"],2)
        self.assertEqual(public["period"]["since"],"2026-01-01")
        self.assertNotIn("cohorts",public)
        self.assertNotIn('"idlead":',json.dumps(public))
        self.assertEqual(len(public["prospects"]),2)
        for since,expected in [(original_day,2),(return_day,2),(new_day,2),(today,1)]:
            selected=[group for group in public["prospects"] if any(
                since.isoformat()<=entry["date"]<=today.isoformat() for entry in group["entries"])]
            self.assertEqual(len(selected),expected)
        group=next(group for group in public["prospects"] if len(group["entries"])==3)
        self.assertTrue(all(entry["stage"]==4 for entry in group["entries"]))
        self.assertTrue(public["sales_link_validated"])
        self.assertNotIn("Cliente fictício", json.dumps(public))


if __name__ == "__main__":
    unittest.main()
