import pandas as pd
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define the path to the historical performance file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_BASE_DIR = os.path.dirname(SCRIPT_DIR)
HISTORICAL_PERF_FILE_PATH = os.path.join(
    PROJECT_BASE_DIR, 
    'results', 
    'long_term_historical_perf', 
    'historical_symbol_performance_long_term.csv'
)

def get_top_historical_picks(n_top: int = 5) -> list:
    """
    Loads historical symbol performance data, selects the top N picks based
    on 'hist_strength_score', and returns their key statistics.

    Args:
        n_top (int): The number of top picks to return. Defaults to 5.

    Returns:
        list: A list of dictionaries, where each dictionary contains the
              'symbol', 'hist_win_rate', 'hist_avg_pnl', and 
              'hist_strength_score' for a top pick. Returns an empty
              list if data cannot be loaded or is insufficient.
    """
    if not os.path.exists(HISTORICAL_PERF_FILE_PATH):
        logger.error(f"Historical performance file not found: {HISTORICAL_PERF_FILE_PATH}")
        return []

    try:
        df = pd.read_csv(HISTORICAL_PERF_FILE_PATH)
    except Exception as e:
        logger.error(f"Error loading historical performance CSV: {e}")
        return []

    if df.empty:
        logger.warning("Historical performance DataFrame is empty.")
        return []

    required_column = 'hist_strength_score'
    if required_column not in df.columns:
        logger.error(f"Required column '{required_column}' not found in the historical performance data.")
        return []

    # Ensure hist_strength_score is numeric and handle potential errors
    df[required_column] = pd.to_numeric(df[required_column], errors='coerce')
    df.dropna(subset=[required_column], inplace=True)  # Remove rows where conversion failed

    # Check if DataFrame became empty after dropping NaN values
    if df.empty:
        logger.warning("Historical performance DataFrame is empty after handling non-numeric scores.")
        return []
        
    # Sort by hist_strength_score in descending order
    df_sorted = df.sort_values(by=required_column, ascending=False)

    # Select the top N rows
    top_n_df = df_sorted.head(n_top)

    if top_n_df.empty:
        logger.info(f"No symbols found after sorting and selecting top {n_top}.")
        return []

    # Extract the required columns
    output_columns = ['symbol', 'hist_win_rate', 'hist_avg_pnl', 'hist_strength_score']
    
    # Check if all desired output columns exist
    missing_cols = [col for col in output_columns if col not in top_n_df.columns]
    if missing_cols:
        logger.warning(f"Missing expected columns in top N data: {', '.join(missing_cols)}. Proceeding with available columns.")
        # Filter output_columns to only include those that exist
        output_columns = [col for col in output_columns if col in top_n_df.columns]
        if not output_columns: # If no relevant columns are left
             logger.error("None of the target output columns are available.")
             return []


    top_n_list = top_n_df[output_columns].to_dict(orient='records')
    
    logger.info(f"Successfully retrieved top {len(top_n_list)} historical picks.")
    return top_n_list

if __name__ == "__main__":
    logger.info("Fetching top historical picks...")
    top_picks = get_top_historical_picks()
    if top_picks:
        print("\nTop Historical Picks:")
        for i, pick in enumerate(top_picks, 1):
            print(f"  Pick {i}:")
            print(f"    Symbol: {pick.get('symbol', 'N/A')}")
            print(f"    Historical Win Rate: {pick.get('hist_win_rate', 'N/A')}")
            print(f"    Historical Avg PnL: {pick.get('hist_avg_pnl', 'N/A')}")
            print(f"    Historical Strength Score: {pick.get('hist_strength_score', 'N/A')}")
    else:
        print("\nNo historical picks found or an error occurred.")
