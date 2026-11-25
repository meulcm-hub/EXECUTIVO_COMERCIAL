import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from refresh_reservas import update_html, read_conditions, pro_amount, verified_reference, key


class RefreshTest(unittest.TestCase):
    def setUp(self):
        self.stock = [{'project':'Projeto A','block':'Bloco A','unit':str(i),'stage':'Etapa A','status':'Disponível'} for i in range(1,4)]
        self.html = 'const D='+json.dumps({'sales':[], 'stock':self.stock, 'audience':{'count':1}})+', SALES=D.sales;'
        self.rows = [{'idreserva':i, 'ativo':'S','situacao':'Vendida','empreendimento':'Projeto A','bloco':'Bloco A','unidade':str(i),
                      'data_venda':'2026-11-02','valor_contrato':100000,'nome_cliente':'Maria Souza Santos','cpf':'00000000000',
                      'idunidade':i, 'condicao':[{'serie':'Financiamento','valor':80000,'pro_soluto':'N'},
                      {'serie':'Parcela 1','valor':10000,'pro_soluto':'S'},
                      {'serie':'Mensal','valor':5000,'pro_soluto':'N'},
                      {'serie':'AdPremiada','idserie':36,'valor':3000,'pro_soluto':'N'},
                      {'serie':'Ch_Moradia','idserie':37,'valor':2000,'pro_soluto':'N'}]} for i in (1,2)]
        self.units = {str(i):{'area_privativa':45+i} for i in (1,2)}

    def refresh(self, html, rows):
        return update_html(html, rows, '2026-11-24', units=self.units)

    def test_publish_and_preserve(self):
        result,count = self.refresh(self.html,self.rows)
        data,_ = json.JSONDecoder().raw_decode(result.split('const D=')[1])
        self.assertEqual(count,2)
        self.assertEqual(len(data['sales']),2)
        self.assertTrue(all(x['id'].startswith('R-') for x in data['sales']))
        self.assertNotIn('Santos',result)
        self.assertNotIn('cpf',result)
        self.assertEqual(sum(x['total'] for x in data['sales']),200000)
        self.assertEqual(sum(x['pro'] for x in data['sales']),20000)
        self.assertEqual(sum(x['m2'] for x in data['sales']),93)
        self.assertEqual(sum(x['net'] for x in data['sales']),190000)
        self.assertEqual(sum(x['adpremiada'] for x in data['sales']),6000)
        self.assertEqual(sum(x['cheque'] for x in data['sales']),4000)
        self.assertTrue(all(x['risk']==0.1 for x in data['sales']))
        self.assertEqual(data['audience'],{'count':1})
        self.assertEqual(self.refresh(result,self.rows)[0],result)

    def test_incomplete_keeps_previous(self):
        with self.assertRaises(ValueError):
            self.refresh(self.html,self.rows[:1])
        with self.assertRaises(ValueError):
            self.refresh(self.html,[{**self.rows[0],'condicao':[]},self.rows[1]])

    def test_explicit_marker_and_reference(self):
        known = {('projetoa','parcela2'):{True,False}, ('projetoa','mensal'):{False}, ('projetoa','anual'):{True}}
        self.assertEqual(pro_amount([{'serie':'Parcela 2','valor':20,'pro_soluto':True},{'serie':'Mensal','valor':100},{'serie':'Anual','valor':30}], 'Projeto A', known),50)
        self.assertEqual(pro_amount([{'serie':'Parcela 2','valor':20,'pro_soluto':False}], 'Projeto A', known),0)
        with self.assertRaises(ValueError):
            pro_amount([{'serie':'Parcela 2','valor':20}], 'Projeto A', known)
        with self.assertRaises(ValueError):
            pro_amount([{'serie':'Desconhecida','valor':20}], 'Projeto A', known)

    def test_area_reference_and_missing(self):
        areas = {key('Projeto A','Bloco A','1'):{48}, key('Projeto A','Bloco A','2'):{49}}
        result,_ = update_html(self.html,self.rows,'2026-11-24',areas=areas)
        data,_ = json.JSONDecoder().raw_decode(result.split('const D=')[1])
        self.assertEqual(sum(x['m2'] for x in data['sales']),97)
        with self.assertRaises(ValueError):
            update_html(self.html,self.rows,'2026-11-24')

    def test_original_reference(self):
        areas, flags = verified_reference()
        self.assertGreater(len(areas),1000)
        self.assertEqual(flags[('','mensal')],{False})
        self.assertEqual(flags[('','parcela1')],{True})
        self.assertEqual(flags[('','parcela2')],{False,True})

    def test_cvdw_official_identity_and_latest_version(self):
        def payload(page):
            rows = [{'idreservascondicoes':11,'idreserva':1,'serie':'Mensal','valor':10000,
                     'parcela_quantidade':10,'ativo':'S','referencia_data':'2026-11-01'},
                    {'idreservascondicoes':11,'idreserva':1,'serie':'Mensal','valor':12000,
                     'parcela_quantidade':10,'ativo':'S','referencia_data':'2026-11-02','pro_soluto':'N'}]
            return {'total_de_registros':2,'total_de_paginas':2,'dados':[rows[page-1]]}
        grouped = read_conditions(payload, {'1'})
        self.assertEqual(grouped, {'1':[{'serie':'Mensal','idserie':None,'valor':12000,'pro_soluto':'N'}]})
        with self.assertRaises(ValueError):
            read_conditions(payload, {'2'})


if __name__ == '__main__':
    unittest.main()
