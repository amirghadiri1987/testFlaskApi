from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# Base directory for client data
BASE_DIR = "/path/to/client_data"

@app.route('/upload_transaction', methods=['POST'])
def upload_transaction():
    client_id = request.headers.get('Client-ID')
    transaction_data = request.json

    # Debugging logs
    print(f"Received Client-ID: {client_id}")
    print(f"Received Transaction Data: {transaction_data}")

    if not client_id:
        return jsonify({"error": "Client-ID missing"}), 400
    if not transaction_data:
        return jsonify({"error": "Transaction data missing or invalid"}), 400

    # Process and save the transaction
    client_dir = os.path.join(BASE_DIR, client_id)
    os.makedirs(client_dir, exist_ok=True)
    transaction_file = os.path.join(client_dir, "transaction.json")
    with open(transaction_file, "a") as file:
        file.write(f"{transaction_data}\n")

    return jsonify({"status": "success"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)  # Bind to all interfaces
