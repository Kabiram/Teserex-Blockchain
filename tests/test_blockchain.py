# tests/test_blockchain.py
import unittest
import os
import shutil
from blockchain import Blockchain

class TestBlockchain(unittest.TestCase):
    def setUp(self):
        # Use a separate test DB directory if desired
        self.bc = Blockchain(config_path='config.yaml')
        self.bc.stop_mining()

    def tearDown(self):
        self.bc.close()
        # Cleanup the RocksDB directory
        if os.path.exists('data/chain_db'):
            shutil.rmtree('data/chain_db', ignore_errors=True)

    def test_genesis_block_exists(self):
        genesis = self.bc.get_block(0)
        self.assertIsNotNone(genesis, "Genesis block was not created.")
        self.assertEqual(genesis.index, 0, "Genesis block index should be 0.")

    def test_mine_block(self):
        initial_block = self.bc.get_latest_block()
        self.bc.mine_block()
        new_block = self.bc.get_latest_block()
        self.assertEqual(new_block.index, initial_block.index + 1, "Blockchain height did not increase.")

if __name__ == '__main__':
    unittest.main()
