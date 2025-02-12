# tests/test_transactions.py
import unittest
from blockchain import Blockchain
from functions.transaction_function import create_transaction

class TestTransactions(unittest.TestCase):
    def setUp(self):
        self.bc = Blockchain(config_path='config.yaml')
        self.bc.stop_mining()

    def tearDown(self):
        self.bc.close()

    def test_create_transaction(self):
        tx = create_transaction("did:teserex:1111", "did:teserex:2222", 50, "Hello", self.bc.config)
        self.assertIn("txid", tx, "Transaction must have a txid.")
        self.assertEqual(tx["amount"], 50, "Amount must match.")
        self.assertIsNotNone(tx["message"], "Encrypted message must exist.")

if __name__ == '__main__':
    unittest.main()
