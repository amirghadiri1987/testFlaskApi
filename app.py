import os
from flask import Flask, request, jsonify

app = Flask(__name__)

# Directory for uploaded files
UPLOAD_FOLDER = './ServerUpload'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure base upload folder exists

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files or 'clientID' not in request.form:
        return jsonify({'error': 'File or clientID not provided'}), 400

    file = request.files['file']
    client_id = request.form['clientID']  # Retrieve clientID from form data

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Create client-specific folder
    client_folder = os.path.join(UPLOAD_FOLDER, client_id)
    os.makedirs(client_folder, exist_ok=True)

    # Save the file to the client-specific folder
    file_path = os.path.join(client_folder, file.filename)
    file.save(file_path)

    return jsonify({'message': 'File uploaded successfully', 'file_path': file_path}), 200
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
