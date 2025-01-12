import os
import time
import pandas as pd
import matplotlib.pyplot as plt

csv_file = r"Experts/test02/BTCUSD_H1.csv"

# Ensure the output directory exists
output_directory = os.path.dirname(csv_file)
if not os.path.exists(output_directory):
    os.makedirs(output_directory)

# Define the output image path
output_image = os.path.join(output_directory, "profit_chart.png")

# Track the last modification time of the CSV file
last_mod_time = None

def generate_chart():
    """
    Generate the profit chart and save it as an image.
    """
    try:
        # Load the CSV file
        data = pd.read_csv(csv_file)

        # Filter rows where the "magic" column equals 11209
        filtered_data = data[data["magic"] == 11209]

        # Plot the "date" vs "profit" as a line graph
        plt.figure(figsize=(10, 6))
        plt.plot(filtered_data["date"], filtered_data["profit"], marker='o', label="Profit")
        plt.title("Profit Over Time (Magic 11209)")
        plt.xlabel("Date")
        plt.ylabel("Profit")
        plt.xticks(rotation=45)
        plt.legend()
        plt.grid()

        # Save the chart as an image
        plt.tight_layout()
        plt.savefig(output_image)
        plt.close()

        print(f"Chart updated: {output_image}")
    except Exception as e:
        print(f"Error generating chart: {e}")

while True:
    try:
        # Check if the CSV file has been updated
        if os.path.exists(csv_file):
            current_mod_time = os.path.getmtime(csv_file)
            if last_mod_time is None or current_mod_time != last_mod_time:
                last_mod_time = current_mod_time
                generate_chart()

        # Wait before checking again
        time.sleep(5)  # Check every 5 seconds
    except KeyboardInterrupt:
        print("Stopped monitoring.")
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
