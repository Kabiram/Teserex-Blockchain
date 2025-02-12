# functions/account_creation_function.py
import os
import json
import uuid
import logging

from Crypto.PublicKey import ECC
from Crypto.Hash import SHA256
from Crypto.Signature import DSS

logger = logging.getLogger(__name__)

def create_account(accounts_dir: str, did_registry: dict = None):
    """
    Creates a new account with an ECC key pair, a DID, etc.
    """
    key = ECC.generate(curve='P-256')
    private_key = key.export_key(format='PEM')
    public_key = key.public_key().export_key(format='PEM')

    # Generate a DID for the user
    did = f"did:teserex:{uuid.uuid4()}"
    
    account_data = {
        "did": did,
        "private_key": private_key,
        "public_key": public_key,
        "balance": 0,  # starting balance
        "roles": []
    }

    # Save to file (on-chain/off-chain approach).
    account_id = did.split(':')[-1]
    file_path = os.path.join(accounts_dir, f"{account_id}.json")
    with open(file_path, 'w') as f:
        json.dump(account_data, f, indent=2)

    logger.info(f"New account created with DID: {did}")
    return account_data
