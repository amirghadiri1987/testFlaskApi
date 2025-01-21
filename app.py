from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# Set the base directory to save files
UPLOAD_FOLDER = '/root/EA_Server/ServerUpload'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/upload_csv', methods=['POST'])
def upload_csv():
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

@app.route('/check_file', methods=['GET'])
def check_file():
    file_path = "/root/EA_Server/ServerUpload/Trade_Transaction.csv"
    
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return jsonify({'status': 'success', 'message': 'File found', 'path': file_path}), 200
    else:
        return jsonify({'status': 'fail', 'message': 'File not found'}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
