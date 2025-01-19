from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# Define the root upload folder
UPLOAD_ROOT = '/root/EA_Server/ServerUpload'
os.makedirs(UPLOAD_ROOT, exist_ok=True)  # Ensure the base upload folder exists

@app.route('/upload/<client_id>', methods=['POST'])
def upload_file(client_id):
    """
    Endpoint to upload a file for a specific client.
    :param client_id: Identifier for the client (e.g., 'client_001')
    """
    # Ensure the client's folder exists
    client_folder = os.path.join(UPLOAD_ROOT, client_id)
    os.makedirs(client_folder, exist_ok=True)

    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Save the file in the client's folder
    file_path = os.path.join(client_folder, file.filename)
    try:
        file.save(file_path)
        return jsonify({'message': f'File uploaded successfully for {client_id}: {file_path}'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
