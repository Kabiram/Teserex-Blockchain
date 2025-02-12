# merkle_tree.py
import hashlib

def hash_data(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def build_merkle_tree(data_list):
    """
    Build Merkle tree from a list of data strings and return the root hash.
    """
    if not data_list:
        return None

    current_level = [hash_data(d) for d in data_list]

    while len(current_level) > 1:
        temp_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i+1] if (i+1 < len(current_level)) else left
            temp_level.append(hash_data(left + right))
        current_level = temp_level

    return current_level[0]
