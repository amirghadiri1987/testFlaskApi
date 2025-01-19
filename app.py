from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# Set the directory to save files
UPLOAD_FOLDER = '/ServerUpload/1001/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return jsonify({'status': 'fail', 'message': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'fail', 'message': 'No selected file'}), 400

    # Save the file
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
    return jsonify({'status': 'success', 'message': 'File uploaded successfully'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
