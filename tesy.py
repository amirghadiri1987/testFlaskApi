from flask import Flask, request, jsonify
import pandas as pd

app = Flask(__name__)

@app.route('/filter_csv', methods=['POST'])
def filter_csv():
    # Get parameters from the request
    input_file = request.form.get('input_file')
    output_file = request.form.get('output_file')
    filter_value = request.form.get('filter_value')
    
    # Load the CSV file and filter based on the filter value
    try:
        data = pd.read_csv(input_file)
        filtered_data = data[data['Open Comment'].str.contains(filter_value)]
        filtered_data.to_csv(output_file, index=False)
        
        return jsonify({"message": "Success", "filtered_rows": len(filtered_data)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
