import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from run_real_demo import BudgetClient, MODEL, MAX_REQUESTS, RESERVATION, BUDGET

class BudgetTests(unittest.TestCase):
    def test_caps_prevent_network(self):
        with tempfile.TemporaryDirectory() as d:
            c=BudgetClient('test',Path(d))
            with patch('urllib.request.urlopen') as network:
                with self.assertRaises(RuntimeError): c.complete('x'*5001,MODEL,0,1)
                with self.assertRaises(RuntimeError): c.complete('x','different-model',0,1)
                c.records=[{}]*MAX_REQUESTS
                with self.assertRaises(RuntimeError): c.complete('x',MODEL,0,1)
                c.records=[]
                c.reserved=BUDGET-RESERVATION/2
                with self.assertRaises(RuntimeError): c.complete('x',MODEL,0,1)
                network.assert_not_called()
    def test_total_budget(self):
        self.assertLess(MAX_REQUESTS*RESERVATION,0.5)
        self.assertLess(MAX_REQUESTS*RESERVATION,BUDGET)
    def test_failed_call_keeps_reservation(self):
        with tempfile.TemporaryDirectory() as d:
            c=BudgetClient('test',Path(d))
            with patch('urllib.request.urlopen',side_effect=TimeoutError) as network:
                with self.assertRaises(RuntimeError): c.complete('x',MODEL,0,1)
                self.assertEqual(network.call_count,1)
                self.assertEqual(len(c.records),1)
                self.assertEqual(c.reserved,RESERVATION)

if __name__=='__main__': unittest.main()
