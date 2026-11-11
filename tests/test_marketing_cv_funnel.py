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

    def test_cv_explicit_sale_flag(self):
        self.assertTrue(funnel.sold({"vendida": "S", "situacao": {"situacao": "Reserva"}}))
        self.assertTrue(funnel.sold({"status_reserva": "Pode Faturar"}))

    def test_cvdw_reservations_multi_lead_string(self):
        self.assertEqual(funnel.lead_ids({"idlead": "168523,4322"}), {"168523", "4322"})
        self.assertEqual(funnel.lead_ids({"idlead": 168523}), {"168523"})

    def test_cvdw_sale_flag(self):
        self.assertTrue(funnel.sold({"venda": "Sim", "situacao": "Pré-vendas"}))
        self.assertTrue(funnel.sold({"situacao": "Pode Faturar"}))

    def test_canceled_not_sale(self):
        for state in ("Cancelada", "Distrato", "Vencida", "Reservada"):
            self.assertFalse(funnel.sold({"situacao": {"situacao": state}}))

    def test_associated_leads_deduplicated(self):
        self.assertEqual(funnel.lead_ids({
            "leads_associados": [{"idlead": 77}, {"idlead": 77}, {"idlead": 88}]
        }), {"77", "88"})

    def test_cvdw_reservas_response_dados(self):
        payload = {"pagina": 1, "registros": 1,
                   "total_de_registros": 1, "total_de_paginas": 1,
                   "dados": [{"idreserva": 12414, "venda": "Sim",
                              "situacao": "Vendida", "idlead": "168523,4322",
                              "data_venda": "2026-11-11 00:00:00"}]}
        self.assertEqual(len(funnel.rows(payload, ("dados",))), 1)
        row = funnel.rows(payload, ("dados",))[0]
        self.assertTrue(funnel.sold(row))
        self.assertEqual(funnel.lead_ids(row), {"168523", "4322"})
        with patch.object(funnel, "get", return_value=payload) as mocked:
            got = funnel.paged("https://lcm.cvcrm.com.br", "a", "b",
                              "/api/v1/cvdw/reservas",
                              __import__("datetime").date(2026, 11, 1),
                              __import__("datetime").date(2026, 11, 11),
                              collection=("dados",))
        self.assertEqual(len(got), 1)
        self.assertEqual(mocked.call_count, 1)

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
