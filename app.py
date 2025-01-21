@app.route('/list_files', methods=['GET'])
def list_files():
    try:
        # List the contents of the base directory
        base_folder = app.config['UPLOAD_FOLDER']
        if not os.path.exists(base_folder):
            return jsonify({'status': 'fail', 'message': f"Directory '{base_folder}' does not exist"}), 404

        contents = {}
        for client_id in os.listdir(base_folder):
            client_folder = os.path.join(base_folder, client_id)
            if os.path.isdir(client_folder):
                contents[client_id] = os.listdir(client_folder)
        
        return jsonify({'status': 'success', 'contents': contents}), 200
    except Exception as e:
        return jsonify({'status': 'fail', 'message': str(e)}), 500
