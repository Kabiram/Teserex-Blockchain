# tests/test_accounts.py
import unittest
import os
import json

from functions.account_creation_function import create_account
from functions.account_management_function import add_role_to_account, remove_role_from_account, load_account

class TestAccounts(unittest.TestCase):
    def setUp(self):
        self.accounts_dir = "data/accounts"
        if not os.path.exists(self.accounts_dir):
            os.makedirs(self.accounts_dir)

    def tearDown(self):
        # Cleanup any created accounts
        for f in os.listdir(self.accounts_dir):
            if f.endswith(".json"):
                os.remove(os.path.join(self.accounts_dir, f))

    def test_create_account(self):
        account = create_account(self.accounts_dir)
        self.assertIn("did", account)

    def test_role_management(self):
        account = create_account(self.accounts_dir)
        account_id = account["did"].split(":")[-1]
        add_role_to_account(self.accounts_dir, account_id, "data_uploader")
        acc_loaded = load_account(self.accounts_dir, account_id)
        self.assertIn("data_uploader", acc_loaded["roles"])

        remove_role_from_account(self.accounts_dir, account_id, "data_uploader")
        acc_loaded = load_account(self.accounts_dir, account_id)
        self.assertNotIn("data_uploader", acc_loaded["roles"])

if __name__ == '__main__':
    unittest.main()
