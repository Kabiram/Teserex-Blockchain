# functions/transaction_function.py
import time
import json
import logging
import hashlib
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from merkle_tree import hash_data

logger = logging.getLogger(__name__)

def _normalize_key(key_str: str, desired_len=32) -> bytes:
    """
    Pads or truncates the user-provided key to 'desired_len' bytes.
    For AES-256, desired_len=32. 
    You could also handle 16 or 24 if you prefer.
    """
    raw_key = key_str.encode('utf-8')
    if len(raw_key) >= desired_len:
        # truncate
        return raw_key[:desired_len]
    else:
        # pad with null bytes up to desired_len
        padding_needed = desired_len - len(raw_key)
        return raw_key + (b'\x00' * padding_needed)

def encrypt_message(key: str, plaintext: str):
    # Ensure key is 32 bytes
    raw_key = _normalize_key(key, 32)
    cipher = AES.new(raw_key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode('utf-8'))
    return {
        'nonce': cipher.nonce.hex(),
        'tag': tag.hex(),
        'ciphertext': ciphertext.hex()
    }

def decrypt_message(key: str, enc_dict: dict):
    raw_key = _normalize_key(key, 32)
    try:
        cipher = AES.new(raw_key, AES.MODE_GCM, nonce=bytes.fromhex(enc_dict['nonce']))
        plaintext = cipher.decrypt_and_verify(
            bytes.fromhex(enc_dict['ciphertext']),
            bytes.fromhex(enc_dict['tag'])
        )
        return plaintext.decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to decrypt message: {e}")
        return None

def calculate_gas_fee(config, message: str, contract_complexity: float = 0.0):
    base_fee = config['gas']['base_fee']
    byte_fee = config['gas']['message_byte_fee']
    complexity_fee = config['gas']['contract_complexity_fee'] * contract_complexity

    # Gas fee = base_fee + (length_of_msg * byte_fee) + complexity_fee
    fee = base_fee + (len(message) * byte_fee) + complexity_fee
    return fee

def create_transaction(sender, receiver, amount, message, config, contract_complexity=0):
    """
    A simplified EUTXO-like transaction format:
    {
        'inputs': [...],   # references to previous unspent outputs
        'outputs': [...],  # new UTXOs
        'metadata': {...}, # e.g. arbitrary data like messages
    }
    """
    timestamp = int(time.time())
    fee = calculate_gas_fee(config, message, contract_complexity)

    # Placeholder for the actual UTXO references (would come from the sender's unspent outputs).
    tx_inputs = [hashlib.sha256(f"{sender}{timestamp}".encode()).hexdigest()]

    # The new UTXO for the receiver
    tx_outputs = [{
        "address": receiver,
        "amount": amount
    }]

    # Optional encryption of message
    encryption_key = config['security']['encryption_key']
    encrypted_msg = encrypt_message(encryption_key, message)

    transaction = {
        "timestamp": timestamp,
        "inputs": tx_inputs,
        "outputs": tx_outputs,
        "sender": sender,
        "receiver": receiver,
        "amount": amount,
        "message": encrypted_msg,  # store encrypted
        "fee": fee
    }

    # A transaction id (txid) can be the hash of the entire tx JSON
    tx_json = json.dumps(transaction, sort_keys=True)
    txid = hash_data(tx_json)
    transaction["txid"] = txid

    logger.info(f"Transaction created: {txid}")
    return transaction
