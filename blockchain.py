# blockchain.py

import json
import time
import logging
import threading

import yaml
from merkle_tree import build_merkle_tree, hash_data
from functions.transaction_function import create_transaction
from wasm_runtime import WASMRuntime
from rocksdict import Rdict, Options

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
#logger.setLevel(self.config['log_level'] or "INFO")

class Block:
    def __init__(self, index, previous_hash, merkle_root, timestamp, transactions, nonce, block_hash):
        self.index = index
        self.previous_hash = previous_hash
        self.merkle_root = merkle_root
        self.timestamp = timestamp
        self.transactions = transactions
        self.nonce = nonce
        self.block_hash = block_hash

    def to_dict(self):
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "nonce": self.nonce,
            "block_hash": self.block_hash
        }


class Blockchain:
    def __init__(self, config_path='config.yaml'):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.db_path = 'data/chain_db'
        self.chain_key = b'chain_height'
        self.mempool = []  # list of pending transactions
        # Configure RocksDB options (tune as needed)
        self.db_options = Options()
        self.db_options.set_keep_log_file_num(1)    # example: keep minimal log files
        self.db_options.set_max_open_files(-1)      # example: allow many open files
        # Optionally tweak more parameters:
        # self.db_options.set_compression_type("lz4")
        # self.db_options.set_create_if_missing(True) # This is True by default in rocksdict

        # Open or create the RocksDB (Rdict) store
        self.db = Rdict(
            self.db_path,
            self.db_options,
        )

        # If chain not initialized, create genesis
        self.init_blockchain()

        self.mining = True
        self.block_time = self.config['blockchain']['block_time_interval_seconds']
        self.consensus = self.config['blockchain']['consensus']
        self.start_mining()
        # Smart contracts init
        self.wasm_runtime = WASMRuntime(self.config, self)

    def init_blockchain(self):
        chain_height = self.db.get(self.chain_key)
        if chain_height is None:
            logger.info("No chain found. Creating genesis block.")
            genesis_block = self.create_block(0, '0'*64, [], 0)
            self.add_block_to_chain(genesis_block)
            logger.info(f"Genesis block created with index {genesis_block.index}")
        else:
            height = int(chain_height.decode())
            # Double-check that the block with this height actually exists
            block0 = self.get_block(0)
            if block0 is None:
                # Possibly a leftover chain_key was set, but no actual block is stored.
                logger.info("chain_key is 0 but block #0 not found. Re-storing genesis.")
                genesis_block = self.create_block(0, '0'*64, [], 0)
                self.add_block_to_chain(genesis_block)
            else:
                logger.info(f"Blockchain height is {height}")

    def get_block(self, index: int):
        block_bytes = self.db.get(str(index).encode())
        if block_bytes is None:
            return None
        block_dict = json.loads(block_bytes.decode('utf-8'))
        return Block(
            block_dict["index"],
            block_dict["previous_hash"],
            block_dict["merkle_root"],
            block_dict["timestamp"],
            block_dict["transactions"],
            block_dict["nonce"],
            block_dict["block_hash"]
        )

    def create_block(self, index, prev_hash, transactions, nonce):
        # Build Merkle root from transactions
        merkle_root = build_merkle_tree([json.dumps(tx, sort_keys=True) for tx in transactions]) or ''
        timestamp = int(time.time() * 1000)

        # Construct block data for hashing
        block_data_str = f"{index}{prev_hash}{merkle_root}{timestamp}{nonce}"
        block_hash = hash_data(block_data_str)

        new_block = Block(index, prev_hash, merkle_root, timestamp, transactions, nonce, block_hash)
        return new_block

    def add_block_to_chain(self, block: Block):
        # Convert block to JSON and store in RocksDB
        block_bytes = json.dumps(block.to_dict()).encode('utf-8')
        self.db[str(block.index).encode()] = block_bytes

        # Update chain height
        self.db[self.chain_key] = str(block.index).encode()

    def get_latest_block(self):
        height_bytes = self.db.get(self.chain_key)
        if height_bytes is None:
            return None
        height = int(height_bytes.decode())
        return self.get_block(height)
    ### better approach exists
    def get_balance(self, did):
        # parse all blocks, sum in - out
        balance = 0
        height_bytes = self.db.get(self.chain_key)
        if not height_bytes:
            return 0
        height = int(height_bytes.decode())
        for i in range(height + 1):
            block = self.get_block(i)
            if not block or not block.transactions:
                continue
            for tx in block.transactions:
                if tx['receiver'] == did:
                    balance += tx['amount']
                if tx['sender'] == did:
                    balance -= tx['amount'] + tx['fee']  # if you want to subtract fee from sender
        return balance

    def get_transactions_for_did(self, did):
        txs = []
        height_bytes = self.db.get(self.chain_key)
        if not height_bytes:
            return []
        height = int(height_bytes.decode())
        for i in range(height + 1):
            block = self.get_block(i)
            if not block or not block.transactions:
                continue
            for tx in block.transactions:
                if tx['receiver'] == did or tx['sender'] == did:
                    txs.append(tx)
        return txs

    def mint(self, to_did, amount):
        """
        Mints 'amount' to the given DID.
        This is effectively creating new tokens.
        We store it as a special transaction in a minted-block
        or we just do an in-memory update if your chain
        scans all blocks for balances.
        """
        # For a simple approach, we create a special transaction
        # with sender="MINT" and receiver=to_did.
        # Then we immediately add it to the chain by forging a block
        # or put it into next block's transactions.

        mint_tx = {
            "timestamp": int(time.time()),
            "inputs": [],
            "outputs": [{"address": to_did, "amount": amount}],
            "sender": "MINT",
            "receiver": to_did,
            "amount": amount,
            "message": "Minting new tokens",
            "fee": 0,
        }
        # We'll generate a txid, etc.
        import json
        from merkle_tree import hash_data

        tx_json = json.dumps(mint_tx, sort_keys=True)
        txid = hash_data(tx_json)
        mint_tx["txid"] = txid

        # If you have a mempool concept:
        # self.mempool.append(mint_tx)
        self.mempool.append(mint_tx)
        logger.info(f"Mint of {amount} to {to_did} added to mempool. Will appear in next mined block.")
        # # or if you do a "create_block" right away:
        # last_block = self.get_latest_block()
        # new_index = last_block.index + 1
        # new_block = self.create_block(new_index, last_block.block_hash, [mint_tx], 0)
        # self.add_block_to_chain(new_block)

        #logger.info(f"Minted {amount} to {to_did}. Block index: {new_index}")
        return mint_tx

    def mine_block(self):
        latest_block = self.get_latest_block()
        new_index = latest_block.index + 1
        new_block = self.create_block(new_index, latest_block.block_hash, self.mempool, 0)

        self.add_block_to_chain(new_block)  # Only once

        # Clear the mempool now that we've included these transactions
        self.mempool = []

        logger.info(f"New block mined with index {new_index} ⛏")
        logger.info(f"Block hash: {new_block.block_hash}")
        logger.info(f"Merkle root: {new_block.merkle_root if new_block.merkle_root else ''}")
        tx_count = len(new_block.transactions) if new_block.transactions else 0
        logger.info(f"Transactions: {tx_count if tx_count else 'None'}")
        logger.info(f"Block {new_index} has been successfully linked 🔗")

    def start_mining(self):
        """
        PoA "mining" thread that continuously creates blocks 
        (even empty) every block_time seconds.
        """
        def mining_loop():
            while self.mining:
                start_time = int(time.time() * 1000)
                self.mine_block()
                end_time = int(time.time() * 1000)
                logger.info(f"(start: {start_time} ms) (end: {end_time} ms)")
                time.sleep(self.block_time)

        t = threading.Thread(target=mining_loop, daemon=True)
        t.start()



    def stop_mining(self):
        self.mining = False

    def create_transaction(self, sender, receiver, amount, message, contract_complexity=0):
        """
        Creates a transaction object with our EUTXO / dynamic gas logic,
        then appends it to the mempool.
        """
        tx = create_transaction(sender, receiver, amount, message, self.config, contract_complexity)
        if tx:
            # Append to mempool so next block can include it
            self.mempool.append(tx)
        return tx
    
    def deploy_smart_contract(self, contract_path, contract_name):
        return self.wasm_runtime.deploy_contract(contract_path, contract_name)

    def close(self):
        # Close the RocksDB dictionary
        self.db.close()

# If you want to run this file directly:
if __name__ == "__main__":
    bc = Blockchain('config.yaml')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bc.stop_mining()
        bc.close()
        logger.info("Blockchain stopped.")
