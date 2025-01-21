from flask import Flask, request, jsonify
import os
import csv

app = Flask(__name__)

# Base directory for uploads
UPLOAD_FOLDER = '/root/EA_Server/ServerUpload'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/check_csv', methods=['POST'])
def check_csv():
    client_id = request.form.get('clientID')
    file_name = request.form.get('fileName')

    # Debugging: Print clientID and fileName
    print(f"Received clientID: {client_id}, fileName: {file_name}")

    if not client_id or not file_name:
        return jsonify({'status': 'fail', 'message': 'Missing clientID or fileName'}), 400

    # Construct file path
    client_folder = os.path.join(app.config['UPLOAD_FOLDER'], client_id)
    file_path = os.path.join(client_folder, file_name)

    # Debugging: Print constructed file path
    print(f"Checking file path: {file_path}")

    # Check if the file exists
    if not os.path.exists(file_path):
        return jsonify({'status': 'fail', 'message': f'File does not exist: {file_path}'}), 404

    # Count rows in the file
    try:
        with open(file_path, 'r') as csv_file:
            row_count = sum(1 for row in csv.reader(csv_file))
        return jsonify({'status': 'success', 'message': 'File exists', 'row_count': row_count, 'path': file_path}), 200
    except Exception as e:
        return jsonify({'status': 'fail', 'message': f'Error reading file: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
