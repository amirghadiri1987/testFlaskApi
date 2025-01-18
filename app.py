from flask import Flask, request, jsonify, send_file
import os
import base64  # For decoding Base64 data
import pandas as pd
import matplotlib.pyplot as plt

app = Flask(__name__)

UPLOAD_FOLDER = '/var/www/vps_env'  # Correct path on your Linux server
os.makedirs(UPLOAD_FOLDER, exist_ok=True)



@app.route('/upload/<client_id>', methods=['POST'])
def upload_file(client_id):
    client_dir = os.path.join(UPLOAD_FOLDER, client_id)
    os.makedirs(client_dir, exist_ok=True)


    if not request.is_json:
         return jsonify({"error": "Request must be JSON"}), 400



    data = request.get_json()
    if 'filename' not in data or 'file' not in data:
         return jsonify({'error': 'Missing filename or file data'}), 400




    filename = data['filename']  # Get the filename from the JSON data
    file_data_base64 = data['file']

    try:
        file_data = base64.b64decode(file_data_base64)  # Decode the Base64 data
    except Exception as e:
        return jsonify({'error': f'Invalid Base64 data: {e}'}), 400


    filepath = os.path.join(client_dir, filename)


    try:
       with open(filepath, 'wb') as f:  # Write the decoded data to the file
            f.write(file_data)

       # ... (Process CSV and generate chart - same as previous examples)...

       return jsonify({'message': 'File uploaded and processed'}), 200

    except Exception as e:
       return jsonify({'error': f'Error saving or processing file: {e}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
