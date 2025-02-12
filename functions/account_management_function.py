# functions/account_management_function.py
import os
import json
import logging

logger = logging.getLogger(__name__)

def load_account(accounts_dir: str, account_id: str):
    file_path = os.path.join(accounts_dir, f"{account_id}.json")
    if not os.path.exists(file_path):
        logger.error(f"Account file not found for {account_id}")
        return None
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

def save_account(accounts_dir: str, account_data: dict):
    account_id = account_data['did'].split(':')[-1]
    file_path = os.path.join(accounts_dir, f"{account_id}.json")
    with open(file_path, 'w') as f:
        json.dump(account_data, f, indent=2)
    logger.debug(f"Account {account_id} updated successfully.")

def add_role_to_account(accounts_dir: str, account_id: str, role: str):
    account_data = load_account(accounts_dir, account_id)
    if account_data is None:
        return
    if role not in account_data['roles']:
        account_data['roles'].append(role)
        save_account(accounts_dir, account_data)
        logger.info(f"Role '{role}' added to account {account_id}.")

def remove_role_from_account(accounts_dir: str, account_id: str, role: str):
    account_data = load_account(accounts_dir, account_id)
    if account_data is None:
        return
    if role in account_data['roles']:
        account_data['roles'].remove(role)
        save_account(accounts_dir, account_data)
        logger.info(f"Role '{role}' removed from account {account_id}.")
