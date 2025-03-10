# Standard Library Imports
import os
import shutil
import csv
import sqlite3
import logging
from datetime import datetime

# Third-Party Imports
import pandas as pd
from flask import Flask, flash, request, jsonify, Response, redirect, url_for, session, abort
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from redis import Redis

# Local Imports
import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app setup
app = Flask(__name__)

# Load configurations from environment variables or config file
app.config['UPLOAD_FOLDER'] = config.UPLOAD_DIR
app.config['CALL_BACK_TOKEN_ADMIN'] = config.call_back_token_admin


# Flask-Limiter (Ensure Redis is running)
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri="redis://localhost:6379"  # Check if Redis is properly configured
)




# Home page with login protection
@app.route('/')
@login_required
def home():
    return Response("Hello World in the page!")



# ==================================================== #
def allowed_file(filename):
    """Check if file has allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in config.allowed_extensions
# ==================================================== #
# TODO some health check url ✅
@app.route(f'/{config.call_back_token_check_server}/v1/ok')
def health_check():
    response_data = {"status": "success", "message": "Server is running"}
    return jsonify(response_data), 200
# ==================================================== #
# TODO Fix simple welcome page ✅
@app.route("/chck")
@limiter.limit("5 per minute")
def hello_world():
    print("Configured upload folder:", config.UPLOAD_DIR)
    return "<p>Hello, World!</p>"
# ==================================================== #
# TODO test function ✅
def get_db_path(client_id):
    """Construct the database path for a given client."""
    return os.path.join(config.UPLOAD_DIR, client_id, config.DATABASE_FILENAME)
# ==================================================== #
# TODO test function ✅
def count_database_rows(client_id):
    """Count the number of rows in the 'trades' table for a given client."""
    db_path = get_db_path(client_id)
    
    if not os.path.exists(db_path):
        return 0
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trades")
            row_count = cursor.fetchone()[0]
        return row_count
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return 0
# ==================================================== #
# TODO test function ✅
def database_exists(client_id):
    """Check if the database exists for a given client."""
    db_path = get_db_path(client_id)
    return os.path.exists(db_path)

# ==================================================== #
# TODO test function ✅
def save_csv_to_database(client_id, csv_path):
    """Save CSV data to the database and return the number of rows saved."""
    db_path = get_db_path(client_id)

    try:
        df = pd.read_csv(csv_path)
        with sqlite3.connect(db_path) as conn:
            df.to_sql("trades", conn, if_exists="replace", index=False)
        row_count = len(df)
        return row_count
    except Exception as e:
        logger.error(f"Failed to process file: {e}")
        return str(e)

# ==================================================== #
# TODO test function ✅
@app.route(f'/{config.call_back_token}/check_and_upload', methods=["POST"])
def check_and_upload():
    """API endpoint to check if a file needs to be uploaded and process it."""
    if request.method != "POST":
        return jsonify({"error": "Method not allowed. Use POST."}), 405

    client_id = request.form.get("clientID")
    rows_mql5 = request.form.get("rows_count")

    if not client_id or rows_mql5 is None:
        return jsonify({"error": "Missing clientID or rows_count"}), 400

    try:
        rows_mql5 = int(rows_mql5)
        if rows_mql5 < 0:
            return jsonify({"error": "Invalid rows_count. Must be a non-negative integer."}), 400
    except ValueError:
        return jsonify({"error": "Invalid rows_count. Must be an integer."}), 400

    client_folder = os.path.join(config.UPLOAD_DIR, client_id)
    os.makedirs(client_folder, exist_ok=True)

    rows_db = count_database_rows(client_id)

    if database_exists(client_id) and rows_db == rows_mql5:
        return jsonify({"message": "No need to upload. Data is up-to-date.", "rows": rows_db}), 200

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    csv_path = os.path.join(client_folder, config.CSV_FILENAME)
    try:
        file.save(csv_path)
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        return jsonify({"error": f"Failed to save file: {str(e)}"}), 500

    try:
        result = save_csv_to_database(client_id, csv_path)
        if isinstance(result, int):
            return jsonify({"message": "File uploaded, saved to database, and deleted", "rows_saved": result}), 201
        else:
            return jsonify({"error": f"Failed to process file: {result}"}), 500
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)

# ==================================================== #
# TODO test function
@app.route("/upload_transaction", methods=["POST"])
def upload_transaction_to_db():
    """
    API endpoint to upload a single trade transaction to the main database
    and update the filtered database after a transaction is closed.
    """
    transaction_data = request.json
    if not transaction_data:
        logger.error("No transaction data provided")
        return jsonify({"error": "Missing transaction data"}), 400

    required_fields = [
        'Open Time', 'Symbol', 'Magic Number', 'Type', 'Volume', 'Open Price',
        'S/L', 'T/P', 'Close Price', 'Close Time', 'Commission', 'Swap',
        'Profit', 'Profit Points', 'Duration', 'Open Comment', 'Close Comment'
    ]

    missing_fields = [field for field in required_fields if field not in transaction_data]
    if missing_fields:
        logger.error(f"Missing required fields: {missing_fields}")
        return jsonify({"error": f"Missing required fields: {missing_fields}"}), 400

    try:
        with sqlite3.connect(config.database_file_path) as conn:
            cur = conn.cursor()

            # Insert the new transaction into the main database
            cur.execute('''
                INSERT INTO Trade_Transaction 
                (open_time, symbol, magic_number, type, volume, open_price, sl, tp, 
                 close_price, close_time, commission, swap, profit, profit_points, 
                 duration, open_comment, close_comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                transaction_data['Open Time'], transaction_data['Symbol'], transaction_data['Magic Number'],
                transaction_data['Type'], transaction_data['Volume'], transaction_data['Open Price'],
                transaction_data['S/L'], transaction_data['T/P'], transaction_data['Close Price'],
                transaction_data['Close Time'], transaction_data['Commission'], transaction_data['Swap'],
                transaction_data['Profit'], transaction_data['Profit Points'], transaction_data['Duration'],
                transaction_data['Open Comment'], transaction_data['Close Comment']
            ))

            conn.commit()

        # **Update the filtered database for the specific magic number**
        client_id = transaction_data.get("Client_ID")  # Ensure this field is available
        magic_number = transaction_data["Magic Number"]

        if client_id:
            success = add_single_transaction(client_id, magic_number, transaction_data)
            if not success:
                logger.warning(f"Failed to update filtered database for Magic_Number {magic_number}")

        logger.info("Transaction uploaded successfully")
        return jsonify({"message": "Transaction uploaded successfully"}), 200

    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return jsonify({"error": "Failed to upload transaction due to a database error"}), 500

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500


# Upload a single transaction (when a transaction is completed)
transaction_data = {
    'Open Time': '2025.01.08 08:08:15',
    'Symbol': 'BTCUSD.',
    'Magic Number': 11085,
    'Type': 'buy',
    'Volume': 0.01,
    'Open Price': 96501.4,
    'S/L': None,
    'T/P': None,
    'Close Price': 96491.3,
    'Close Time': '2025.01.08 08:10:04',
    'Commission': -0.78,
    'Swap': 0,
    'Profit': -0.1,
    'Profit Points': -1010,
    'Duration': '0:01:49',
    'Open Comment': 'Break EA 651',
    'Close Comment': ''
}

# ==================================================== #
# TODO test function ✅
def create_filtered_database(client_id, magic_number):
    """
    Ensures the filtered database exists and is up to date based on Magic_Number.
    """
    original_db_path = os.path.join(config.UPLOAD_DIR, client_id, config.DATABASE_FILENAME)
    filtered_db_path = os.path.join(config.UPLOAD_DIR, client_id, f"filtered_{magic_number}.db")

    if not os.path.exists(original_db_path):
        logger.error(f"Original database not found: {original_db_path}")
        return None

    try:
        # Read transactions for the specified Magic_Number from the original database
        with sqlite3.connect(original_db_path) as conn:
            query = "SELECT * FROM trades WHERE Magic_Number = ?"
            df = pd.read_sql_query(query, conn, params=(magic_number,))

        # If no transactions are found, return None
        if df.empty:
            logger.warning(f"No transactions found for Magic_Number {magic_number}.")
            return None

        # Save the filtered transactions to the filtered database
        with sqlite3.connect(filtered_db_path) as conn:
            df.to_sql("filtered_trades", conn, if_exists="replace", index=False)

        logger.info(f"Filtered database created/updated for Magic_Number {magic_number}.")
        return filtered_db_path

    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None

# ==================================================== #
# TODO test function ✅
def calculate_outputs(filtered_db_path):
    """
    Calculates the required outputs from the filtered database.
    """
    try:
        with sqlite3.connect(filtered_db_path) as conn:
            query = "SELECT * FROM filtered_trades"
            df = pd.read_sql_query(query, conn)
    except sqlite3.Error as e:
        logger.error(f"Error reading from the filtered database: {e}")
        return None

    if df.empty:
        logger.warning("No trades found in the filtered database.")
        return None

    try:
        # Calculate outputs
        outputs = {
            "Most_Volume": float(df["Volume"].max()),
            "First_Open_Time": str(df["Open_Time"].min()),
            "Last_Close_Time": str(df["Close_Time"].max()),
            "Total_Profit": float(df["Profit"].sum()),
            "Drawdown": float(calculate_drawdown(df["Profit"])),
            "Profit_Factor": float(calculate_profit_factor(df["Profit"])),
            "Trades_Won": int(calculate_trades_won_percentage(df["Profit"])[0]),
            "Trades_Won_Percentage": float(calculate_trades_won_percentage(df["Profit"])[1]),
            "Expected_Payoff": float(calculate_expected_payoff(df["Profit"]))
        }
        return outputs
    except Exception as e:
        logger.error(f"Error calculating outputs: {e}")
        return None

# ==================================================== #
# TODO test function ✅ 
def calculate_drawdown(profit_series):
    """
    Calculates the maximum drawdown from a series of profits.
    """
    cumulative_profit = profit_series.cumsum()
    max_drawdown = (cumulative_profit.cummax() - cumulative_profit).max()
    return max_drawdown

# ==================================================== #
# TODO test function ✅
def calculate_profit_factor(profit_series):
    """
    Calculates the profit factor (gross profits / gross losses).
    """
    gross_profits = profit_series[profit_series > 0].sum()
    gross_losses = abs(profit_series[profit_series < 0].sum())
    return gross_profits / gross_losses if gross_losses != 0 else 0

# ==================================================== #
# TODO test function ✅
def calculate_trades_won_percentage(profit_series):
    """
    Calculates the percentage of winning trades and the number of winning trades.
    """
    # Count the number of winning trades (Profit > 0)
    winning_trades = profit_series[profit_series > 0].count()
    
    # Total number of trades
    total_trades = profit_series.count()
    
    # Calculate the percentage of winning trades
    if total_trades > 0:
        win_percentage = (winning_trades / total_trades) * 100
    else:
        win_percentage = 0
    
    return winning_trades, win_percentage

# ==================================================== #
# TODO test function ✅
def calculate_expected_payoff(profit_series):
    """
    Calculates the expected payoff (average profit per trade).
    """
    return profit_series.mean() if not profit_series.empty else 0

# ==================================================== #
# TODO test function ✅
def get_filtered_outputs(client_id, magic_number):
    """
    Main function to get the filtered outputs.
    """
    filtered_db_path = create_filtered_database(client_id, magic_number)
    if not filtered_db_path:
        return {"error": "Failed to create or access the filtered database."}

    outputs = calculate_outputs(filtered_db_path)
    if not outputs:
        return {"error": "Failed to calculate outputs."}

    return outputs

# ==================================================== #
# TODO test function ✅
@app.route(f'/{config.call_back_token_sync}/get_filtered_outputs', methods=["GET"])
def api_get_filtered_outputs():
    client_id = request.args.get("client_id")
    magic_number = request.args.get("magic_number")

    if not client_id or not magic_number:
        return jsonify({"error": "Missing client_id or magic_number"}), 400

    try:
        magic_number = int(magic_number)
    except ValueError:
        return jsonify({"error": "Invalid magic_number. Must be an integer."}), 400

    outputs = get_filtered_outputs(client_id, magic_number)
    if "error" in outputs:
        return jsonify(outputs), 500

    return jsonify(outputs), 200

# ==================================================== #
# TODO test function ✅
def add_single_transaction(client_id, magic_number, transaction_data):
    """
    Adds a single transaction to the filtered database if it matches the Magic_Number.
    """
    filtered_db_path = os.path.join(config.UPLOAD_DIR, client_id, f"filtered_{magic_number}.db")

    if not os.path.exists(filtered_db_path):
        logger.error(f"Filtered database for Magic_Number {magic_number} does not exist.")
        return False

    if transaction_data.get("Magic_Number") != magic_number:
        logger.info("Transaction does not match the specified Magic_Number.")
        return False

    try:
        df_new = pd.DataFrame([transaction_data])
        with sqlite3.connect(filtered_db_path) as conn:
            df_new.to_sql("filtered_trades", conn, if_exists="append", index=False)
        logger.info(f"Added new transaction to filtered database for Magic_Number {magic_number}.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

# ==================================================== #
# ==================================================== #




if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)
