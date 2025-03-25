# Standard Library Imports 108
import os
import shutil
import csv
import sqlite3
import logging
from datetime import datetime

# Third-Party Imports
import pandas as pd
import numpy as np
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

# # Initialize Flask-Login
# login_manager = LoginManager()
# login_manager.init_app(app)





# ==================================================== #
# TODO some health check url ✅
@app.route(f'/{config.call_back_token_check_server}/v1/ok')
def health_check():
    response_data = {"status": "success", "message": "Server is running"}
    return jsonify(response_data), 200

# ==================================================== #
def allowed_file(filename):
    """Check if file has allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in config.allowed_extensions

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
    API endpoint to upload a single trade transaction to the main database.
    """
    transaction_data = request.json
    if not transaction_data:
        logger.error("No transaction data provided")
        return jsonify({"error": "Missing transaction data"}), 400

    # Normalize keys in transaction_data to lowercase
    transaction_data = {k.lower(): v for k, v in transaction_data.items()}

    required_fields = [
        'open_time', 'symbol', 'magic_number', 'type', 'volume', 'open_price',
        's_l', 't_p', 'close_price', 'close_time', 'commission', 'swap',
        'profit', 'profit_points', 'duration', 'open_comment', 'close_comment',
        'floating_drawdown', 'floating_drawdown_currency'  # New columns
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
                 duration, open_comment, close_comment, floating_drawdown, floating_drawdown_currency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                transaction_data['open_time'], transaction_data['symbol'], transaction_data['magic_number'],
                transaction_data['type'], transaction_data['volume'], transaction_data['open_price'],
                transaction_data['s/l'], transaction_data['t/p'], transaction_data['close_price'],
                transaction_data['close_time'], transaction_data['commission'], transaction_data['swap'],
                transaction_data['profit'], transaction_data['profit_points'], transaction_data['duration'],
                transaction_data['open_comment'], transaction_data['close_comment'],
                transaction_data['floating_drawdown'], transaction_data['floating_drawdown_currency']
            ))

            conn.commit()

        # **Update the filtered database for the specific magic number**
        client_id = transaction_data.get("client_id")  # Ensure this field is available
        magic_number = transaction_data["magic_number"]

        if not client_id:
            logger.error("Client_ID is missing in the transaction data.")
            return jsonify({"error": "Client_ID is required to update the filtered database"}), 400

        success = add_single_transaction(client_id, magic_number, transaction_data)
        if not success:
            logger.warning(f"Failed to update filtered database for Magic_Number {magic_number}")
            return jsonify({"error": "Failed to update filtered database"}), 500

        logger.info("Transaction uploaded successfully")
        return jsonify({"message": "Transaction uploaded successfully"}), 200

    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return jsonify({"error": "Failed to upload transaction due to a database error"}), 500

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500










# ==================================================== #
# TODO test function
def create_filtered_database(client_id, magic_number):
    """
    Ensures the filtered database exists and is up to date based on Magic_Number.
    """
    original_db_path = os.path.join(config.UPLOAD_DIR, client_id, config.DATABASE_FILENAME)
    filtered_db_path = os.path.join(config.UPLOAD_DIR, client_id, f"filtered_{magic_number}.db")

    if not os.path.exists(original_db_path):
        logger.error(f"Original database not found: {original_db_path}")
        return {"status": "error", "message": "Original database not found"}

    try:
        # Read transactions for the specified Magic_Number from the original database
        with sqlite3.connect(original_db_path) as conn:
            query = "SELECT * FROM trades WHERE Magic_Number = ?"
            df = pd.read_sql_query(query, conn, params=(magic_number,))

        # If no transactions are found, return a warning
        if df.empty:
            logger.warning(f"No transactions found for Magic_Number {magic_number}.")
            return {"status": "warning", "message": "No transactions found for the specified Magic_Number"}

        # Save the filtered transactions to the filtered database
        with sqlite3.connect(filtered_db_path) as conn:
            # Create the filtered_trades table if it doesn't exist
            df.head(0).to_sql("filtered_trades", conn, if_exists="replace", index=False)
            # Insert the filtered data
            df.to_sql("filtered_trades", conn, if_exists="append", index=False)

        logger.info(f"Filtered database created/updated for Magic_Number {magic_number}.")
        return {"status": "success", "message": "Filtered database created/updated", "path": filtered_db_path}

    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return {"status": "error", "message": f"Database error: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"status": "error", "message": f"Unexpected error: {e}"}

# ==================================================== #
# TODO test function ✅
def get_filtered_outputs(client_id, magic_number):
    """
    Main function to get the filtered outputs.
    """
    # Step 1: Create or update the filtered database
    create_result = create_filtered_database(client_id, magic_number)
    if create_result["status"] != "success":
        return {"error": f"Failed to create or access the filtered database: {create_result['message']}"}

    filtered_db_path = create_result["path"]

    # Step 2: Calculate outputs from the filtered database
    outputs = calculate_outputs(filtered_db_path)
    if not outputs:
        return {"error": "Failed to calculate outputs."}

    return outputs

# ==================================================== #
# TODO test function ✅
@app.route(f'/{config.call_back_token_sync}/get_filtered_outputs', methods=["GET"])
def api_get_filtered_outputs():
    """
    API endpoint to get filtered outputs for a specific client and magic number.
    """
    # Step 1: Validate input parameters
    client_id = request.args.get("client_id")
    magic_number = request.args.get("magic_number")

    if not client_id or not magic_number:
        logger.error("Missing client_id or magic_number")
        return jsonify({"error": "Missing client_id or magic_number"}), 400

    try:
        magic_number = int(magic_number)
    except ValueError:
        logger.error(f"Invalid magic_number: {magic_number}")
        return jsonify({"error": "Invalid magic_number. Must be an integer."}), 400

    # Step 2: Get filtered outputs
    logger.info(f"Fetching filtered outputs for client_id={client_id}, magic_number={magic_number}")
    outputs = get_filtered_outputs(client_id, magic_number)

    # Step 3: Handle errors
    if "error" in outputs:
        logger.error(f"Failed to get filtered outputs: {outputs['error']}")
        return jsonify({"error": "An internal error occurred while processing your request."}), 500

    # Step 4: Return successful response
    logger.info(f"Successfully fetched filtered outputs for client_id={client_id}, magic_number={magic_number}")
    return jsonify(outputs), 200

# ==================================================== #
# TODO test function ✅
def calculate_outputs(filtered_db_path):
    """
    Perform calculations on the filtered database and return the results.
    """
    if not os.path.exists(filtered_db_path):
        logger.error(f"Filtered database not found: {filtered_db_path}")
        return None

    try:
        # Connect to the filtered database
        with sqlite3.connect(filtered_db_path) as conn:
            # Read the filtered data into a DataFrame
            query = "SELECT * FROM filtered_trades"
            df = pd.read_sql_query(query, conn)

        # Check if the DataFrame is empty
        if df.empty:
            logger.warning("No data found in the filtered database.")
            return None

        # Normalize column names by stripping whitespace and converting to lowercase
        df.columns = df.columns.str.strip().str.lower()

        # Debugging: Print column names
        logger.info(f"Columns in DataFrame: {df.columns.tolist()}")

        # Convert date columns to datetime
        df["open_time"] = pd.to_datetime(df["open_time"])
        df["close_time"] = pd.to_datetime(df["close_time"])

        # Perform calculations using smaller functions
        outputs = {
            "Most_Volume": calculate_most_volume(df),
            "smallest_open_time": get_smallest_open_time(df),
            "largest_close_time": get_largest_close_time(df),
            "total_profit": calculate_total_profit(df),
            "profit_factor": calculate_profit_factor(df),
            "trades_won_percentage": calculate_trades_won_percentage(df),
            "expected_payoff": calculate_expected_payoff(df),
            "netProfit": calculate_net_profit(df),
            "NetLoss": calculate_net_loss(df),
            "Balance_mDD": calculate_balance_max_drawdown(df),
            **calculate_drawdown(df),
            **calculate_max_min_drawdowns(df),
            **calculate_floating_drawdown(df),
            **calculate_quantity_metrics(df),
            **calculate_profitability_metrics(df),
            **calculate_profit_distribution(df),
            **calculate_time_metrics(df),
            **calculate_time_extremes(df),
            **calculate_win_loss_metrics(df),
            **calculate_closure_metrics(df),
            **calculate_additional_metrics(df)
        }

        # Print Test Output
        print("\n====== TEST OUTPUT ======")
        for key, value in outputs.items():
            print(f"{key}: {value}")
        print("=================================")

        logger.info("Calculations completed successfully.")
        return outputs

    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None











# ==================================================== #
# TODO test function ✅
def calculate_most_volume(df):
    """
    Calculate the maximum volume from the "Volume" column and return it as a float with two decimal places.

    Parameters:
        df (pd.DataFrame): DataFrame containing a "Volume" column.

    Returns:
        float: Maximum volume rounded to two decimal places.
    """
    most_volume = df["volume"].max()
    return round(float(most_volume), 2)

# ==================================================== #
# TODO test function ✅
def get_smallest_open_time(df):
    """Find the smallest date in the Open_Time column."""
    return df["open_time"].min().strftime("%Y-%m-%d")

# ==================================================== #
# TODO test function ✅
def get_largest_close_time(df):
    """Find the largest date in the Close_Time column."""
    return df["close_time"].max().strftime("%Y-%m-%d")

# ==================================================== #
# TODO test function ✅
def calculate_total_profit(df):
    """Calculate the total profit."""
    total_profit = df["profit"].sum()
    return round(total_profit, 2)

# ==================================================== #
# TODO test function ✅
def calculate_drawdown(df):
    """
    Calculate total drawdown and separate drawdowns for Buy and Sell trades.
    Ensures percentages sum correctly.

    Parameters:
        df (pd.DataFrame): DataFrame with "profit" and "order_type" columns.

    Returns:
        dict: Drawdown values formatted as "$(%)".
    """
    if df.empty or "profit" not in df.columns:
        return {"drawdown": "0.00 (0)", "drawdown_buy": "0.00 (0)", "drawdown_sell": "0.00 (0)"}

    df = df.sort_index()

    def calculate_drawdown_for_subset(sub_df):
        if sub_df.empty:
            return 0.00, 0.00

        sub_df = sub_df.copy()
        sub_df["peak"] = sub_df["profit"].cummax()
        drawdown_dollar = (sub_df["peak"] - sub_df["profit"]).max()
        peak_value = sub_df["peak"].max()

        drawdown_percent = (drawdown_dollar / peak_value * 100) if peak_value > 0 else 0
        drawdown_percent = min(drawdown_percent, 100)  # Cap at 100%

        return drawdown_dollar, drawdown_percent

    # Calculate total drawdown
    total_dd, total_dd_pct = calculate_drawdown_for_subset(df)

    # Calculate buy/sell drawdowns
    if "order_type" in df.columns:
        df["order_type"] = df["order_type"].astype(str).str.lower()
        buy_dd, _ = calculate_drawdown_for_subset(df[df["order_type"] == "buy"])
        sell_dd, _ = calculate_drawdown_for_subset(df[df["order_type"] == "sell"])
    else:
        buy_dd, sell_dd = 0.00, 0.00

    # Ensure total drawdown matches buy + sell
    if abs(total_dd - (buy_dd + sell_dd)) > 1e-2:
        total_dd = buy_dd + sell_dd  

    # Fix percentage distribution
    buy_pct = (buy_dd / total_dd * total_dd_pct) if total_dd > 0 else 0
    sell_pct = (sell_dd / total_dd * total_dd_pct) if total_dd > 0 else 0

    return {
        "drawdown": f"{total_dd:.2f} ({total_dd_pct:.2f})",
        "drawdown_buy": f"{buy_dd:.2f} ({buy_pct:.2f})",
        "drawdown_sell": f"{sell_dd:.2f} ({sell_pct:.2f})"
    }

# ==================================================== #
# TODO test function ✅
def calculate_max_min_drawdowns(df):
    """
    Calculate maximum and minimum drawdowns for total, buy, and sell trades.

    Parameters:
        df (pd.DataFrame): DataFrame with "profit" and "order_type" columns.

    Returns:
        dict: Formatted maximum and minimum drawdown results.
    """
    if df.empty or "profit" not in df.columns or "order_type" not in df.columns:
        return {}

    # Calculate cumulative maximum profit (peak)
    df["peak"] = df["profit"].cummax()

    # Total Drawdowns
    drawdowns_total = df["peak"] - df["profit"]
    max_drawdown_total = drawdowns_total.max()
    min_drawdown_total = drawdowns_total[drawdowns_total > 0].min() if any(drawdowns_total > 0) else 0

    # Maximum and Minimum Drawdown for Buy Trades
    buy_df = df[df["order_type"] == "buy"]
    if not buy_df.empty:
        drawdowns_buy = buy_df["peak"] - buy_df["profit"]
        max_drawdown_buy = drawdowns_buy.max()
        min_drawdown_buy = drawdowns_buy[drawdowns_buy > 0].min() if any(drawdowns_buy > 0) else 0
    else:
        max_drawdown_buy = min_drawdown_buy = 0

    # Maximum and Minimum Drawdown for Sell Trades
    sell_df = df[df["order_type"] == "sell"]
    if not sell_df.empty:
        drawdowns_sell = sell_df["peak"] - sell_df["profit"]
        max_drawdown_sell = drawdowns_sell.max()
        min_drawdown_sell = drawdowns_sell[drawdowns_sell > 0].min() if any(drawdowns_sell > 0) else 0
    else:
        max_drawdown_sell = min_drawdown_sell = 0

    # Calculate percentages based on peak value
    peak_value = df["peak"].max()
    if peak_value > 0:
        max_drawdown_total_pct = (max_drawdown_total / peak_value) * 100
        min_drawdown_total_pct = (min_drawdown_total / peak_value) * 100 if min_drawdown_total > 0 else 0
        max_drawdown_buy_pct = (max_drawdown_buy / peak_value) * 100
        min_drawdown_buy_pct = (min_drawdown_buy / peak_value) * 100 if min_drawdown_buy > 0 else 0
        max_drawdown_sell_pct = (max_drawdown_sell / peak_value) * 100
        min_drawdown_sell_pct = (min_drawdown_sell / peak_value) * 100 if min_drawdown_sell > 0 else 0
    else:
        max_drawdown_total_pct = max_drawdown_buy_pct = max_drawdown_sell_pct = 0
        min_drawdown_total_pct = min_drawdown_buy_pct = min_drawdown_sell_pct = 0

    # Return formatted results
    return {
        "max_drawdown": f"{max_drawdown_total:.2f} ({max_drawdown_total_pct:.2f})",
        "max_drawdown_buy": f"{max_drawdown_buy:.2f} ({max_drawdown_buy_pct:.2f})",
        "max_drawdown_sell": f"{max_drawdown_sell:.2f} ({max_drawdown_sell_pct:.2f})",
        "min_drawdown": f"{min_drawdown_total:.2f} ({min_drawdown_total_pct:.2f})",
        "min_drawdown_buy": f"{min_drawdown_buy:.2f} ({min_drawdown_buy_pct:.2f})",
        "min_drawdown_sell": f"{min_drawdown_sell:.2f} ({min_drawdown_sell_pct:.2f})"
    }

# ==================================================== #
# TODO test function ✅
def calculate_floating_drawdown(df):
    """
    Calculate floating drawdown in both dollar and percentage terms for the entire dataset,
    as well as separately for "Buy" and "Sell" types. Also compute the maximum and minimum
    values for each floating drawdown metric.

    Parameters:
        df (pd.DataFrame): DataFrame containing "floating_drawdown", "floating_drawdown_currency",
                           and "order_type" columns.

    Returns:
        dict: A dictionary containing:
              - "drawdown_floating": Dictionary with "current", "max", and "min" for overall floating drawdown.
              - "drawdown_floating_buy": Dictionary with "current", "max", and "min" for "Buy" trades.
              - "drawdown_floating_sell": Dictionary with "current", "max", and "min" for "Sell" trades.
    """
    # Initialize results dictionary with default values
    results = {
        "drawdown_floating": {
            "drawdown_floating_current": "N/A (N/A)",
            "drawdown_floating_max": "N/A (N/A)",
            "drawdown_floating_min": "N/A (N/A)"
        },
        "drawdown_floating_buy": {
            "drawdown_floating_buy_current": "N/A (N/A)",
            "drawdown_floating_buy_max": "N/A (N/A)",
            "drawdown_floating_buy_min": "N/A (N/A)"
        },
        "drawdown_floating_sell": {
            "drawdown_floating_sell_current": "N/A (N/A)",
            "drawdown_floating_sell_max": "N/A (N/A)",
            "drawdown_floating_sell_min": "N/A (N/A)"
        }
    }

    # Check if DataFrame is empty
    if df.empty:
        return results

    # Ensure the DataFrame is sorted by index (or time) if not already
    df = df.sort_index()

    # Calculate floating drawdown for the entire dataset
    if not df.empty:
        current_val = f"{df['floating_drawdown_currency'].iloc[-1]:.2f} ({df['floating_drawdown'].iloc[-1]:.2f})" if not df.empty else "N/A (N/A)"
        results["drawdown_floating"] = {
            "drawdown_floating_current": current_val,
            "drawdown_floating_max": f"{df['floating_drawdown_currency'].max():.2f} ({df['floating_drawdown'].max():.2f})",
            "drawdown_floating_min": f"{df['floating_drawdown_currency'].min():.2f} ({df['floating_drawdown'].min():.2f})"
        }

    # Calculate floating drawdown for "Buy" trades
    buy_df = df[df["order_type"].str.lower() == "buy"]
    if not buy_df.empty:
        results["drawdown_floating_buy"] = {
            "drawdown_floating_buy_current": f"{buy_df['floating_drawdown_currency'].iloc[-1]:.2f} ({buy_df['floating_drawdown'].iloc[-1]:.2f})",
            "drawdown_floating_buy_max": f"{buy_df['floating_drawdown_currency'].max():.2f} ({buy_df['floating_drawdown'].max():.2f})",
            "drawdown_floating_buy_min": f"{buy_df['floating_drawdown_currency'].min():.2f} ({buy_df['floating_drawdown'].min():.2f})"
        }

    # Calculate floating drawdown for "Sell" trades
    sell_df = df[df["order_type"].str.lower() == "sell"]
    if not sell_df.empty:
        results["drawdown_floating_sell"] = {
            "drawdown_floating_sell_current": f"{sell_df['floating_drawdown_currency'].iloc[-1]:.2f} ({sell_df['floating_drawdown'].iloc[-1]:.2f})",
            "drawdown_floating_sell_max": f"{sell_df['floating_drawdown_currency'].max():.2f} ({sell_df['floating_drawdown'].max():.2f})",
            "drawdown_floating_sell_min": f"{sell_df['floating_drawdown_currency'].min():.2f} ({sell_df['floating_drawdown'].min():.2f})"
        }

    return results

# ==================================================== #
# TODO test function ✅
def calculate_profit_factor(df):
    """Calculate the profit factor."""
    winning_trades = df[df["profit"] > 0]
    losing_trades = df[df["profit"] < 0]
    total_winning_profit = winning_trades["profit"].sum()
    total_losing_loss = abs(losing_trades["profit"].sum())
    # Calculate profit factor and round to two decimal places
    profit_factor = total_winning_profit / total_losing_loss if total_losing_loss != 0 else 0
    return round(profit_factor, 2)
# ==================================================== #
# TODO test function ✅
def calculate_trades_won_percentage(df):
    """Calculate the total trades and win rate."""
    total_trades = len(df)
    winning_trades_count = len(df[df["profit"] > 0])
    win_rate = (winning_trades_count / total_trades) * 100 if total_trades != 0 else 0
    return f"{total_trades} ({win_rate:.2f} %)"

# ==================================================== #
# TODO test function ✅
def calculate_expected_payoff(df):
    """Calculate the expected payoff."""
    total_profit = df["profit"].sum()
    total_trades = len(df)
    expected_payoff = total_profit / total_trades if total_trades != 0 else 0
    return round(expected_payoff, 2)

# ==================================================== #
# TODO test function ✅
def calculate_net_profit(df):
    """Calculate the net profit (sum of positive profits)."""
    net_profit = df[df["profit"] > 0]["profit"].sum()
    return round(net_profit, 2)

# ==================================================== #
# TODO test function ✅
def calculate_net_loss(df):
    """Calculate the net loss (sum of negative profits)."""
    net_loss = df[df["profit"] < 0]["profit"].sum()
    return round(net_loss, 2)

# ==================================================== #
# TODO test function ✅
def calculate_balance_max_drawdown(df):
    """Calculate the ratio of total profit to maximum drawdown."""
    total_profit = df["profit"].sum()
    max_drawdown = df["floating_drawdown"].max()
    balance_max_drawdown = total_profit / max_drawdown if max_drawdown != 0 else 0
    return round(balance_max_drawdown, 2)

# ==================================================== #
# TODO test function ✅
def calculate_quantity_metrics(df):
    """Calculate buy and sell quantities and their percentages."""
    total_trades = len(df)
    buy_trades = df[df["order_type"].str.lower() == "buy"]
    sell_trades = df[df["order_type"].str.lower() == "sell"]
    buy_quantity = len(buy_trades)
    sell_quantity = len(sell_trades)
    buy_percentage = (buy_quantity / total_trades) * 100 if total_trades != 0 else 0
    sell_percentage = (sell_quantity / total_trades) * 100 if total_trades != 0 else 0
    return {
        "Quantity": total_trades,
        "Quantity_Buy": f"{buy_quantity} ({buy_percentage:.2f})",
        "Quantity_Sell": f"{sell_quantity} ({sell_percentage:.2f})"
    }

# ==================================================== #
# TODO test function ✅
def calculate_profitability_metrics(df):
    """Calculate profitable trades and their percentages."""
    total_trades = len(df)
    profitable_trades = df[df["profit"] > 0]
    buy_trades = df[df["order_type"].str.lower() == "buy"]
    sell_trades = df[df["order_type"].str.lower() == "sell"]
    profitable_buy_trades = buy_trades[buy_trades["profit"] > 0]
    profitable_sell_trades = sell_trades[sell_trades["profit"] > 0]
    
    profitable_percentage = (len(profitable_trades) / total_trades) * 100 if total_trades != 0 else 0
    profitable_buy_percentage = (len(profitable_buy_trades) / len(buy_trades)) * 100 if len(buy_trades) != 0 else 0
    profitable_sell_percentage = (len(profitable_sell_trades) / len(sell_trades)) * 100 if len(sell_trades) != 0 else 0
    
    return {
        "Profitable": f"{len(profitable_trades)} ({profitable_percentage:.2f})",
        "Profitable_Buy": f"{len(profitable_buy_trades)} ({profitable_buy_percentage:.2f})",
        "Profitable_Sell": f"{len(profitable_sell_trades)} ({profitable_sell_percentage:.2f})"
    }

# ==================================================== #
# TODO test function ✅
def format_time_delta(total_seconds):
    """Convert total seconds to days:hours:minutes format."""
    days = int(total_seconds // 86400)  # 24 * 3600
    hours = int((total_seconds % 86400) // 3600)
    minutes = int((total_seconds % 3600) // 60)
    return f"{days:02}:{hours:02}:{minutes:02}"

# ==================================================== #
# TODO test function ✅
def calculate_closure_metrics(df):
    """
    Calculate trade closure reasons (Order, SL, TP) based on the "close_reason" column.
    Returns:
        dict: A dictionary with three keys:
              - "Closed_by_Order": Count and percentage of trades closed for reasons other than SL or TP.
              - "Closed_by_SL": Count and percentage of trades closed by stop-loss.
              - "Closed_by_TP": Count and percentage of trades closed by take-profit.
    """
    # Normalize column names by stripping whitespace and converting to lowercase
    df.columns = df.columns.str.strip().str.lower()

    # Ensure the "close_reason" column exists
    if "close_reason" not in df.columns:
        raise ValueError("The 'close_reason' column is missing in the DataFrame.")

    # Total number of trades
    total_trades = len(df)

    # Count trades by closure reason
    closed_by_sl = df[df["close_reason"] == "sl"]
    closed_by_tp = df[df["close_reason"] == "tp"]
    closed_by_order = df[~df["close_reason"].isin(["sl", "tp"])]  # All reasons except SL and TP

    closed_by_order_count = len(closed_by_order)
    closed_by_sl_count = len(closed_by_sl)
    closed_by_tp_count = len(closed_by_tp)

    # Calculate percentages
    closed_by_order_percentage = (closed_by_order_count / total_trades) * 100 if total_trades != 0 else 0
    closed_by_sl_percentage = (closed_by_sl_count / total_trades) * 100 if total_trades != 0 else 0
    closed_by_tp_percentage = (closed_by_tp_count / total_trades) * 100 if total_trades != 0 else 0

    # Return the results
    return {
        "Closed_by_Order": f"{closed_by_order_count} ({closed_by_order_percentage:.2f})",
        "Closed_by_SL": f"{closed_by_sl_count} ({closed_by_sl_percentage:.2f})",
        "Closed_by_TP": f"{closed_by_tp_count} ({closed_by_tp_percentage:.2f})"
    }
# ==================================================== #
# TODO test function ✅
def calculate_profit_distribution(df):
    """
    Calculate profit distribution for buy and sell trades.
    Returns:
        A dictionary with the following keys:
        - "profit_Buy": Total profit from buy trades and its percentage of total profit.
        - "profit_Sell": Total profit from sell trades and its percentage of total profit.
    """
    # Filter buy and sell trades
    buy_trades = df[df["order_type"].str.lower() == "buy"]
    sell_trades = df[df["order_type"].str.lower() == "sell"]

    # Calculate total profit from buy and sell trades
    profit_buy = buy_trades["profit"].sum()
    profit_sell = sell_trades["profit"].sum()

    # Calculate total profit
    total_profit = df["profit"].sum()

    # Calculate percentages
    profit_buy_percentage = (profit_buy / total_profit) * 100 if total_profit != 0 else 0
    profit_sell_percentage = (profit_sell / total_profit) * 100 if total_profit != 0 else 0

    # Ensure percentages are non-negative when profit is zero
    if profit_buy == 0:
        profit_buy_percentage = 0.0
    if profit_sell == 0:
        profit_sell_percentage = 0.0

    # Format the results
    return {
        "profit_Buy": f"{profit_buy:.2f} ({profit_buy_percentage:.2f})",
        "profit_Sell": f"{profit_sell:.2f} ({profit_sell_percentage:.2f})"
    }

# ==================================================== #
# TODO test function ✅
def calculate_time_extremes(df):
    """Calculate max and min open time."""
    df["duration"] = pd.to_timedelta(df["duration"])
    max_open_time = df["duration"].max().total_seconds()
    min_open_time = df["duration"].min().total_seconds()
    return {
        "Max_Open_Time": format_time_delta(max_open_time),
        "Min_Open_Time": format_time_delta(min_open_time)
    }

# ==================================================== #
# TODO test function ✅
def calculate_win_loss_metrics(df):
    """Calculate biggest win, average win, biggest loss, and average loss, rounded to two decimal places."""
    winning_trades = df[df["profit"] > 0]
    losing_trades = df[df["profit"] < 0]
    
    biggest_win = round(winning_trades["profit"].max(), 2) if not winning_trades.empty else 0
    average_win = round(winning_trades["profit"].mean(), 2) if not winning_trades.empty else 0
    biggest_loss = round(losing_trades["profit"].min(), 2) if not losing_trades.empty else 0
    average_loss = round(losing_trades["profit"].mean(), 2) if not losing_trades.empty else 0
    
    return {
        "Biggest_Win": biggest_win,
        "Average_Win": average_win,
        "Biggest_Loss": biggest_loss,
        "Average_Loss": average_loss
    }

# ==================================================== #
# TODO test function ✅
def calculate_time_metrics(df):
    """
    Calculate time-based metrics.
    
    Parameters:
        df (pd.DataFrame): DataFrame containing "duration" and "order_type" columns.
        
    Returns:
        dict: A dictionary containing time-based metrics.
    """
    # Ensure the "duration" column is in timedelta format
    if not pd.api.types.is_timedelta64_dtype(df["duration"]):
        df["duration"] = pd.to_timedelta(df["duration"], unit="s")

    # Calculate total open time in seconds
    total_open_time = df["duration"].sum().total_seconds()

    # Filter buy and sell trades
    buy_trades = df[df["order_type"].str.lower() == "buy"]
    sell_trades = df[df["order_type"].str.lower() == "sell"]

    # Calculate total open time for buy and sell trades
    buy_open_time = buy_trades["duration"].sum().total_seconds()
    sell_open_time = sell_trades["duration"].sum().total_seconds()

    # Calculate average open times
    avg_open_time = total_open_time / len(df) if len(df) != 0 else 0
    avg_buy = buy_open_time / len(buy_trades) if len(buy_trades) != 0 else 0
    avg_sell = sell_open_time / len(sell_trades) if len(sell_trades) != 0 else 0

    # Calculate percentages for buy and sell open times
    buy_percentage = (buy_open_time / total_open_time) * 100 if total_open_time != 0 else 0
    sell_percentage = (sell_open_time / total_open_time) * 100 if total_open_time != 0 else 0

    # Calculate max and min open times
    max_open_time = df["duration"].max().total_seconds()
    min_open_time = df["duration"].min().total_seconds()

    # Return the results
    return {
        "Open_Time": format_time_delta(total_open_time),
        "Open_Time_Buy": f"{format_time_delta(buy_open_time)} ({buy_percentage:.2f})",
        "Open_Time_Sell": f"{format_time_delta(sell_open_time)} ({sell_percentage:.2f})",
        "Avg_Open_Time": format_time_delta(avg_open_time),
        "Avg_Buy": format_time_delta(avg_buy),
        "Avg_Sell": format_time_delta(avg_sell),
        "Max_Open_Time": format_time_delta(max_open_time),
        "Min_Open_Time": format_time_delta(min_open_time)
    }

# ==================================================== #
# TODO test function ✅
def calculate_additional_metrics(df):
    """
    Calculate additional trading metrics based on the DataFrame.

    Parameters:
        df (pd.DataFrame): DataFrame containing trading data with columns like "profit", "order_type",
                           "duration", "lots", "commission", "swap", etc.

    Returns:
        dict: A dictionary containing the following metrics:
              - "max_flat_period": Maximum flat period in days:hours:minutes format.
              - "max_drawdown_time": Maximum drawdown time in days:hours:minutes format.
              - "max_drawdown_trades": Number of trades during the maximum drawdown period.
              - "most_winning_trades": Most winning trades in "count (total_profit)" format.
              - "most_losing_trades": Most losing trades in "count (total_loss)" format.
              - "winning_streak": Winning streak in "total_profit (count)" format.
              - "losing_streak": Losing streak in "total_loss (count)" format.
              - "sum_lots": Total sum of lots traded.
              - "sum_commission": Total commission in "total_commission (percentage)" format.
              - "sum_swap": Total swap in "total_swap (percentage)" format.
    """
    # Ensure the DataFrame is sorted by index (or time) if not already
    df = df.sort_index()

    # Initialize results dictionary
    results = {}

    # 1. Max Flat Period
    max_flat_period = df["duration"].max().total_seconds()
    results["max_flat_period"] = format_time_delta(max_flat_period)

    # 2. Max Drawdown Time
    df["peak"] = df["profit"].cummax()
    drawdown = df["peak"] - df["profit"]
    max_drawdown_time = df.loc[drawdown.idxmax(), "duration"].total_seconds()
    results["max_drawdown_time"] = format_time_delta(max_drawdown_time)

    # 3. Max Drawdown Trades
    max_drawdown_trades = len(df[df["profit"] < df["peak"]])
    results["max_drawdown_trades"] = max_drawdown_trades

    # 4. Most Winning Trades
    winning_trades = df[df["profit"] > 0]
    most_winning_trades_count = len(winning_trades)
    most_winning_trades_profit = winning_trades["profit"].sum()
    results["most_winning_trades"] = f"{most_winning_trades_count} ({most_winning_trades_profit:.2f} USD)"

    # 5. Most Losing Trades
    losing_trades = df[df["profit"] < 0]
    most_losing_trades_count = len(losing_trades)
    most_losing_trades_loss = losing_trades["profit"].sum()
    results["most_losing_trades"] = f"{most_losing_trades_count} ({most_losing_trades_loss:.2f} USD)"

    # 6. Winning Streak
    winning_streak = df[df["profit"] > 0]["profit"].sum()
    winning_streak_count = len(df[df["profit"] > 0])
    results["winning_streak"] = f"{winning_streak:.2f} USD ({winning_streak_count})"

    # 7. Losing Streak
    losing_streak, losing_streak_count = calculate_losing_streak(df)
    results["losing_streak"] = f"{losing_streak:.2f} USD ({losing_streak_count})"

    # 8. Sum Lots
    sum_lots = round(df["volume"].sum(), 2)  # Round to 2 decimal places
    results["sum_lots"] = sum_lots

    # 9. Sum Commission
    sum_commission = df["commission"].sum()
    commission_percentage = (sum_commission / df["profit"].sum()) * 100 if df["profit"].sum() != 0 else 0
    results["sum_commission"] = f"{sum_commission:.2f} USD ({commission_percentage:.2f})"

    # 10. Sum Swap
    sum_swap = df["swap"].sum()
    swap_percentage = (sum_swap / df["profit"].sum()) * 100 if df["profit"].sum() != 0 else 0
    results["sum_swap"] = f"{sum_swap:.2f} USD ({swap_percentage:.2f})"

    return results

# ==================================================== #
# TODO test function ✅
def format_time_delta(total_seconds):
    """Convert total seconds to days:hours:minutes format."""
    days = int(total_seconds // (24 * 3600))
    total_seconds %= 24 * 3600
    hours = int(total_seconds // 3600)
    total_seconds %= 3600
    minutes = int(total_seconds // 60)
    return f"{days}:{hours:02}:{minutes:02}"

# ==================================================== #
# TODO test function ✅
def calculate_losing_streak(df):
    """
    Calculate the losing streak (longest sequence of consecutive losing trades).

    Parameters:
        df (pd.DataFrame): DataFrame containing trading data with a "profit" column.

    Returns:
        float: Total loss during the losing streak.
        int: Number of trades in the losing streak.
    """
    losing_streak_loss = 0
    losing_streak_count = 0
    current_streak_loss = 0
    current_streak_count = 0

    for profit in df["profit"]:
        if profit < 0:
            current_streak_loss += profit
            current_streak_count += 1
        else:
            if current_streak_loss < losing_streak_loss:
                losing_streak_loss = current_streak_loss
                losing_streak_count = current_streak_count
            current_streak_loss = 0
            current_streak_count = 0

    # Check the last streak
    if current_streak_loss < losing_streak_loss:
        losing_streak_loss = current_streak_loss
        losing_streak_count = current_streak_count

    return losing_streak_loss, losing_streak_count

# ==================================================== #
# TODO test function ✅


# ==================================================== #
# TODO test function ✅





































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
    
































if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8010)
