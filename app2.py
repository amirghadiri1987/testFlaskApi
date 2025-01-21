from flask import Flask, request, jsonify
import os
import csv

app = Flask(__name__)

# Set the base directory to save files
UPLOAD_FOLDER = '/root/EA_Server/ServerUpload'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/check_csv', methods=['POST'])
def check_csv():
    """
    Check if a CSV file exists for a client and return the number of rows.
    """
    client_id = request.form.get('clientID')
    file_name = request.form.get('fileName')

    if not client_id or not file_name:
        return jsonify({'status': 'fail', 'message': 'Missing clientID or fileName'}), 400

    # Construct the file path
    client_folder = os.path.join(app.config['UPLOAD_FOLDER'], client_id)
    file_path = os.path.join(client_folder, file_name)

    # Check if the file exists
    if not os.path.exists(file_path):
        return jsonify({'status': 'fail', 'message': 'File does not exist'}), 404

    # Count the number of rows in the CSV file
    try:
        with open(file_path, 'r') as csv_file:
            row_count = sum(1 for _ in csv.reader(csv_file))
        return jsonify({'status': 'success', 'message': 'File exists', 'rows': row_count}), 200
    except Exception as e:
        return jsonify({'status': 'fail', 'message': f'Error reading the file: {str(e)}'}), 500


@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    """
    Upload a CSV file for a client.
    """
    client_id = request.form.get('clientID')
    if not client_id:
        return jsonify({'status': 'fail', 'message': 'Missing clientID'}), 400

    if 'file' not in request.files:
        return jsonify({'status': 'fail', 'message': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'fail', 'message': 'No selected file'}), 400

    # Create a unique folder for the client
    client_folder = os.path.join(app.config['UPLOAD_FOLDER'], client_id)
    os.makedirs(client_folder, exist_ok=True)

    # Save the file in the client's folder
    file_path = os.path.join(client_folder, file.filename)
    file.save(file_path)

    return jsonify({'status': 'success', 'message': 'File uploaded successfully', 'path': file_path}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
