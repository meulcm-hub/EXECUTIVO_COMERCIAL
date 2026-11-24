import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from refresh_reservas import update_html, read_conditions


class RefreshTest(unittest.TestCase):
    def setUp(self):
        self.stock = [{'project':'Projeto A','block':'Bloco A','unit':str(i),'stage':'Etapa A','status':'Disponível'} for i in range(1,4)]
        self.html = 'const D='+json.dumps({'sales':[], 'stock':self.stock, 'audience':{'count':1}})+', SALES=D.sales;'
        self.rows = [{'idreserva':i, 'ativo':'S','situacao':'Vendida','empreendimento':'Projeto A','bloco':'Bloco A','unidade':str(i),
                      'data_venda':'2026-11-02','valor_contrato':100000,'nome_cliente':'Maria Souza Santos','cpf':'00000000000',
                      'condicao':[{'serie':'Financiamento','valor':90000},{'serie':'Mensal','valor':10000}]} for i in (1,2)]

    def test_publish_and_preserve(self):
        result,count = update_html(self.html,self.rows,'2026-11-24')
        data,_ = json.JSONDecoder().raw_decode(result.split('const D=')[1])
        self.assertEqual(count,2)
        self.assertEqual(len(data['sales']),2)
        self.assertTrue(all(x['id'].startswith('R-') for x in data['sales']))
        self.assertNotIn('Santos',result)
        self.assertNotIn('cpf',result)
        self.assertEqual(sum(x['total'] for x in data['sales']),200000)
        self.assertEqual(sum(x['pro'] for x in data['sales']),20000)
        self.assertEqual(data['audience'],{'count':1})
        self.assertEqual(update_html(result,self.rows,'2026-11-24')[0],result)

    def test_incomplete_keeps_previous(self):
        with self.assertRaises(ValueError):
            update_html(self.html,self.rows[:1],'2026-11-24')
        with self.assertRaises(ValueError):
            update_html(self.html,[{**self.rows[0],'condicao':[]},self.rows[1]],'2026-11-24')

    def test_cvdw_official_identity_and_latest_version(self):
        def payload(page):
            rows = [{'idreservascondicoes':11,'idreserva':1,'serie':'Mensal','valor':10000,
                     'parcela_quantidade':10,'ativo':'S','referencia_data':'2026-11-01'},
                    {'idreservascondicoes':11,'idreserva':1,'serie':'Mensal','valor':12000,
                     'parcela_quantidade':10,'ativo':'S','referencia_data':'2026-11-02'}]
            return {'total_de_registros':2,'total_de_paginas':2,'dados':[rows[page-1]]}
        grouped = read_conditions(payload, {'1'})
        self.assertEqual(grouped, {'1':[{'serie':'Mensal','idserie':None,'valor':12000}]})
        with self.assertRaises(ValueError):
            read_conditions(payload, {'2'})


if __name__ == '__main__':
    unittest.main()
