import os
import pandas as pd
import matplotlib.pyplot as plt

def generate_graph(input_file, output_file):
    # Verify the input file exists
    if not os.path.exists(input_file):
        return f"Error: Input file '{input_file}' does not exist."

    # Verify the script has write permissions for the output directory
    output_dir = os.path.dirname(output_file)
    if not os.access(output_dir, os.W_OK):
        return f"Error: No write permissions for the directory '{output_dir}'."

    try:
        # Read the CSV into a pandas DataFrame
        df = pd.read_csv(input_file)
        print("Data preview:")
        print(df.head())

        # Convert 'Open Time' column to datetime
        df['Open Time'] = pd.to_datetime(df['Open Time'], errors='coerce')

        # Check if the necessary columns exist
        if 'Open Time' in df.columns and 'Profit' in df.columns:
            # Plot the data
            plt.figure(figsize=(10, 6))
            plt.plot(df['Open Time'], df['Profit'], label='Profit Over Time', color='blue')
            plt.title('Transaction Profit Data')
            plt.xlabel('Open Time')
            plt.ylabel('Profit')
            plt.xticks(rotation=45)
            plt.grid(True)
            plt.legend()
            plt.tight_layout()

            # Save the plot as a PNG image
            plt.savefig(output_file)
            plt.close()

            return f"Graph generated and saved successfully to '{output_file}'."
        else:
            return "Error: Columns 'Open Time' and 'Profit' not found in the CSV."

    except Exception as e:
        return f"An error occurred while processing the file: {str(e)}"

# Use fixed Linux-style paths
input_csv = "C:/Users/amirghadiri/AppData/Roaming/MetaQuotes/Terminal/DF61353BF8A1A742719A92383DEF4BE0/MQL5/Files/Break EA/Aron Markets Ltd/Transaction.csv"
output_image = "C:/Users/amirghadiri/AppData/Roaming/MetaQuotes/Terminal/DF61353BF8A1A742719A92383DEF4BE0/MQL5/Files/Break EA/Aron Markets Ltd/10984/AnalysisOutput/Transaction10984_plot.png"

# Call the function and print the result
result = generate_graph(input_csv, output_image)
print(result)
