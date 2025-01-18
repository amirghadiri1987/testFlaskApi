from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/upload_transaction', methods=['POST'])
def upload_transaction():
    # Handle the incoming data
    client_id = request.headers.get('Client-ID')
    data = request.get_json()
    # Process the transaction data here
    return jsonify({"status": "success", "client_id": client_id, "data": data})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
