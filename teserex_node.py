import logging
import os
import yaml
import json
import hashlib
from flask import Flask, request, redirect, url_for, render_template, session, jsonify, send_file
from blockchain import Blockchain
from p2p_network import StompServerClient
from functions.account_creation_function import create_account
from functions.account_management_function import load_account, add_role_to_account, save_account
from functions.transaction_function import decrypt_message
from wasm_runtime import WASMRuntime
from datetime import datetime

########################
#  Load Config & Setup
########################

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

logging.basicConfig(level=config.get('log_level', 'INFO'))
logger = logging.getLogger(__name__)

# Create the blockchain instance (core functions remain unchanged)
bc = Blockchain(config_path='config.yaml')

# Set up STOMP client (if applicable)
stomp_host = config['network']['stomp_host']
stomp_port = config['network']['stomp_port']
try:
    stomp_client = StompServerClient(stomp_host, stomp_port)
    stomp_client.start()
except Exception as e:
    logger.warning(f"Could not connect to STOMP server: {e}")

# Initialize WASM runtime (for market smart contract)
wasm_runtime = WASMRuntime(config, bc)

########################
#  Flask Dashboard/App
########################

app = Flask(__name__, template_folder='dashboard_templates')
app.secret_key = 'some-random-secret'  # For session management

# Custom filter to format timestamps.
@app.template_filter('datetimeformat')
def datetimeformat(value):
    return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')

@app.route('/')
def index():
    # Home page with version and external links.
    return render_template('index.html', version="1.00.00")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    else:
        # For the new UI, login via email and password.
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            return "Missing email or password", 400
        # For simplicity, search for an account whose email matches.
        accounts_dir = 'data/accounts'
        account = None
        for fname in os.listdir(accounts_dir):
            if fname.endswith(".json"):
                acc = load_account(accounts_dir, fname[:-5])
                if acc.get("email") == email:
                    account = acc
                    break
        if not account:
            return "Account not found", 404
        provided_hash = hashlib.sha256(password.encode()).hexdigest()
        if provided_hash == account.get('password_hash'):
            session['did'] = account['did']
            # Set session permanence based on "Remember Me"
            session.permanent = True if request.form.get('remember_me') else False
            return redirect(url_for('tx_console'))
        else:
            return "Invalid password", 401

@app.route('/create_account', methods=['GET', 'POST'])
def create_account_route():
    if request.method == 'GET':
        return render_template('create_account.html')
    else:
        email = request.form.get('email')
        password = request.form.get('password')
        organization = request.form.get('organization')
        if not password or not email or not organization:
            return "Email, organization and password are required", 400
        account = create_account('data/accounts')
        account['email'] = email
        account['organization'] = organization
        account['password_hash'] = hashlib.sha256(password.encode()).hexdigest()
        save_account('data/accounts', account)
        # By default, assign the role "user"
        add_role_to_account('data/accounts', account['did'].split(':')[-1], 'user')
        session['did'] = account['did']
        return redirect(url_for('tx_console'))

@app.route('/tx_console', methods=['GET'])
def tx_console():
    if 'did' not in session:
        return redirect(url_for('login'))
    did = session['did']
    balance = bc.get_balance(did)
    tx_history = bc.get_transactions_for_did(did)
    # For testing, minting is now visible to everyone.
    return render_template('tx_console.html', did=did, balance=balance, tx_history=tx_history)

@app.route('/send_transaction', methods=['POST'])
def send_transaction():
    if 'did' not in session:
        return redirect(url_for('login'))
    sender = session['did']
    receiver = request.form.get('receiver')
    amount = float(request.form.get('amount', 0))
    message = request.form.get('message', '')
    tx = bc.create_transaction(sender, receiver, amount, message)
    return redirect(url_for('tx_console'))

@app.route('/mint', methods=['POST'])
def mint():
    if 'did' not in session:
        return "Not logged in", 401
    to_did = request.form.get('to_did')
    amount = float(request.form.get('amount', 0))
    bc.mint(to_did, amount)
    return redirect(url_for('tx_console'))

@app.route('/blocks', methods=['GET'])
def get_blocks():
    chain_height_bytes = bc.db.get(bc.chain_key)
    if chain_height_bytes is None:
        return jsonify([]), 200
    chain_height = int(chain_height_bytes.decode())
    blocks = []
    for i in range(chain_height + 1):
        b = bc.get_block(i)
        if b:
            blocks.append(b.to_dict())
    return jsonify(blocks), 200

@app.route('/search_tx', methods=['GET'])
def search_tx():
    txid = request.args.get('txid')
    chain_height_bytes = bc.db.get(bc.chain_key)
    found_tx = None
    if chain_height_bytes:
        chain_height = int(chain_height_bytes.decode())
        for i in range(chain_height + 1):
            block = bc.get_block(i)
            if block and block.transactions:
                for tx in block.transactions:
                    if tx.get('txid') == txid:
                        found_tx = tx
                        break
            if found_tx:
                break
    return render_template('search_result.html', tx=found_tx, txid=txid)

# --- Contract Deployment and Invocation Routes ---

@app.route('/deploy_contract', methods=['POST'])
def deploy_contract():
    # Deploy a WASM contract.
    # You can either upload a file or specify a path.
    if 'file' in request.files:
        file = request.files.get('file')
        if not file:
            return "No file uploaded", 400
        temp_path = "/tmp/" + file.filename
        file.save(temp_path)
    else:
        temp_path = request.form.get('contract_path')
        if not temp_path or not os.path.isfile(temp_path):
            return "Invalid contract path", 400
    contract_name = request.form.get('contract_name', 'UnnamedContract')
    contract_hash = wasm_runtime.deploy_contract(temp_path, contract_name)
    if contract_hash:
        return "Contract deployed with hash: " + contract_hash
    else:
        return "Deployment failed", 400

@app.route('/invoke_contract', methods=['POST'])
def invoke_contract():
    contract_hash = request.form.get('contract_hash')
    function_name = request.form.get('function_name')
    result = wasm_runtime.execute_contract(contract_hash, function_name)
    return "Invoked " + function_name + " on contract hash " + contract_hash + " with result: " + str(result)

# Marketplace routes

@app.route('/marketplace', methods=['GET'])
def marketplace():
    # Use the market contract state from wasm_runtime.
    listings = list(wasm_runtime.market_contract_state.values())
    return render_template('marketplace.html', listings=listings, session=session)

@app.route('/create_listing', methods=['GET', 'POST'])
def create_listing():
    if 'did' not in session:
        return redirect(url_for('login'))
    if request.method == 'GET':
        return render_template('create_listing.html')
    else:
        seller_did = session['did']
        file_path = request.form.get('file_path')
        price = float(request.form.get('price'))
        duration_days = int(request.form.get('duration_days'))
        description = request.form.get('description')
        # Set pending listing data in wasm_runtime.
        wasm_runtime.pending_listing = {
            "seller_did": seller_did,
            "file_path": file_path,
            "price": price,
            "duration_days": duration_days,
            "description": description
        }
        # Invoke the market contract's create_listing function.
        market_contract_hash = request.form.get('contract_hash')
        result = wasm_runtime.execute_contract(market_contract_hash, "create_listing")
        if result != 0:
            return "Failed to create listing via smart contract", 400
        return redirect(url_for('marketplace'))

@app.route('/buy_listing', methods=['POST'])
def buy_listing():
    if 'did' not in session:
        return redirect(url_for('login'))
    buyer_did = session['did']
    listing_id = request.form.get('listing_id')
    # Set pending purchase data in wasm_runtime.
    wasm_runtime.pending_purchase = (listing_id, buyer_did)
    market_contract_hash = request.form.get('contract_hash')
    result = wasm_runtime.execute_contract(market_contract_hash, "purchase_listing")
    if result != 0:
        return "Purchase failed", 400
    return redirect(url_for('marketplace'))

@app.route('/download_file', methods=['GET'])
def download_file():
    user_did = session.get('did')
    listing_id = request.args.get('listing_id')
    if not listing_id:
        return "Listing ID required", 400
    if listing_id not in wasm_runtime.market_contract_state:
        return "Listing not found", 404
    listing = wasm_runtime.market_contract_state[listing_id]
    if listing.get("buyer_did") != user_did:
        return "You haven't purchased this file", 403
    file_path = listing.get("file_path")
    return send_file(file_path, mimetype="text/plain")

def main():
    host = config['server']['host']
    port = config['server']['port']
    app.run(host=host, port=port, debug=False)

if __name__ == '__main__':
    main()
