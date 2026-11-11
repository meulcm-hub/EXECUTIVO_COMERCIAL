"""Testes sem credenciais ou dados pessoais para o funil comercial."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import marketing_cv_funnel as funnel


class FunnelRulesTests(unittest.TestCase):
    def test_sale_statuses_approved(self):
        for state in ("Pode Faturar", "Vendido", "Contrato Assinado",
                      "Aguardando Assinatura Interna", "Enviado para UAU",
                      "Boleto/PIX", "Faturado"):
            with self.subTest(state=state):
                self.assertTrue(funnel.sold({"situacao": {"situacao": state}}))

    def test_canceled_not_sale(self):
        for state in ("Cancelada", "Distrato", "Vencida", "Reservada"):
            self.assertFalse(funnel.sold({"situacao": {"situacao": state}}))

    def test_associated_leads_deduplicated(self):
        self.assertEqual(funnel.lead_ids({
            "leads_associados": [{"idlead": 77}, {"idlead": 77}, {"idlead": 88}]
        }), {"77", "88"})

    def test_precadastro_paginates_by_total(self):
        payloads = [
            {"total": 3, "limite": 2, "pagina": 1,
             "precadastros": [{"idprecadastro": 1}, {"idprecadastro": 2}]},
            {"total": 3, "limite": 2, "pagina": 2,
             "precadastros": [{"idprecadastro": 3}]},
        ]
        with patch.object(funnel, "PAGE_SIZE", 2), patch.object(
                funnel, "get", side_effect=payloads) as mocked:
            results = funnel.paged("https://lcm.cvcrm.com.br", "a", "b",
                                   "/api/v1/comercial/precadastro",
                                   __import__("datetime").date(2026, 1, 1),
                                   __import__("datetime").date(2026, 2, 1),
                                   collection=("precadastros",), precadastro=True)
        self.assertEqual(len(results), 3)
        self.assertEqual(mocked.call_count, 2)


if __name__ == "__main__":
    unittest.main()
