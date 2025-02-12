# wasm_runtime.py
import os
import time
import logging
import hashlib
import threading
import json
import uuid

from wasmtime import Memory, MemoryType, Limits, Func, FuncType, ValType, Global, GlobalType, Engine, Store, Module, Instance, Func, WasmtimeError

logger = logging.getLogger(__name__)

class WASMRuntime:
    def __init__(self, config, blockchain_ref):
        """
        :param config: Parsed config.yaml as a Python dict.
        :param blockchain_ref: Reference to the Blockchain instance.
        """
        self.config = config
        self.blockchain = blockchain_ref
        # Create a Wasmtime Engine.
        self.engine = Engine()
        # Global state for our market contract.
        # market_contract_state stores listing data: { listing_id: { ... } }
        self.market_contract_state = {}
        # Globals to pass data from Flask to host functions.
        self.pending_listing = None      # For seller: details to create a new listing.
        self.pending_purchase = None     # For buyer: tuple (listing_id, buyer_did).

    def deploy_contract(self, contract_binary_path, contract_name):
        """
        Reads a compiled WASM file, stores it in the blockchain DB, and returns a unique contract_hash.
        """
        logger.info(f"Deploying WASM Contract: {contract_name} from {contract_binary_path}")

        if not os.path.isfile(contract_binary_path):
            logger.error("Contract file not found.")
            return None

        with open(contract_binary_path, 'rb') as f:
            wasm_bytes = f.read()

        contract_hash = hashlib.sha256(wasm_bytes).hexdigest()

        key = b'contract:' + contract_hash.encode('utf-8')
        existing = self.blockchain.db.get(key)
        if existing is None:
            self.blockchain.db.put(key, wasm_bytes)
            logger.info(f"Contract {contract_name} stored with hash {contract_hash}")
        else:
            logger.info(f"Contract {contract_name} already exists with hash {contract_hash}")

        return contract_hash

    def execute_contract(self, contract_hash, function_name, **kwargs):
        """
        Loads the WASM from chain DB, instantiates it, and calls an exported function.
        Extra keyword arguments are ignored here because we use globals to pass data.
        """
        # Fetch wasm bytes.
        key = b'contract:' + contract_hash.encode('utf-8')
        wasm_bytes = self.blockchain.db.get(key)
        if not wasm_bytes:
            logger.error(f"No contract found for hash {contract_hash}")
            return None

        try:
            module = Module(self.engine, wasm_bytes)
        except Exception as e:
            logger.error(f"Failed to compile WASM module: {e}")
            return None

        # Create a fresh Store.
        store = Store(self.engine)

        # Build the import object with our host functions.
        import_object = self._build_import_object(store)

        try:
            instance = Instance(store, module, import_object)
        except Exception as e:
            logger.error(f"Failed to instantiate contract: {e}")
            return None

        # Call the exported function.
        try:
            exports = instance.exports(store)
            if function_name not in exports:
                logger.error(f"Exported function '{function_name}' not found in contract.")
                return None

            func = exports[function_name]
            logger.info(f"Executing function '{function_name}'")
            result = func(store)
            return result
        except WasmtimeError:
            logger.error("WASM contract execution error (possibly ran out of gas)!")
            return None
        except Exception as e:
            logger.error(f"Error calling function '{function_name}': {e}")
            return None


    def _build_import_object(self, store):
        # Host function for creating a listing.
        def host_create_listing(store_) -> int:
            if self.pending_listing is None:
                logger.error("No pending listing found in host_create_listing")
                return -1
            listing = self.pending_listing.copy()
            listing_id = str(uuid.uuid4())
            listing["listing_id"] = listing_id
            listing["status"] = "active"
            listing["listing_created_at"] = int(time.time())
            listing["available_until"] = listing["listing_created_at"] + (listing["duration_days"] * 24 * 3600)
            self.market_contract_state[listing_id] = listing
            logger.info(f"Market listing created: {listing}")
            self.pending_listing = None
            return 0

        # Host function for purchasing a listing.
        def host_purchase_listing(store_) -> int:
            if self.pending_purchase is None:
                logger.error("No pending purchase data found in host_purchase_listing")
                return -1
            listing_id, buyer_did = self.pending_purchase
            if listing_id not in self.market_contract_state:
                logger.error("Listing not found in market_contract_state")
                return -1
            listing = self.market_contract_state[listing_id]
            if listing["status"] != "active":
                logger.error("Listing is not active")
                return -1
            if int(time.time()) > listing["available_until"]:
                logger.error("Listing has expired")
                return -1
            buyer_balance = self.blockchain.get_balance(buyer_did)
            if buyer_balance < listing["price"]:
                logger.error("Insufficient funds for purchase")
                return -1
            tx = self.blockchain.create_transaction(buyer_did, listing["seller_did"], listing["price"], "Market purchase")
            listing["status"] = "sold"
            listing["buyer_did"] = buyer_did
            self.market_contract_state[listing_id] = listing
            logger.info(f"Listing {listing_id} purchased by {buyer_did}")
            self.pending_purchase = None
            return 0

        create_listing_type = FuncType([], [ValType.i32()])
        purchase_listing_type = FuncType([], [ValType.i32()])

        create_listing_func = Func(store, create_listing_type, host_create_listing)
        purchase_listing_func = Func(store, purchase_listing_type, host_purchase_listing)

        import_object = {
            "env": {
                "host_create_listing": create_listing_func,
                "host_purchase_listing": purchase_listing_func,
            }
        }
        return import_object