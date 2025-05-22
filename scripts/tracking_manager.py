import pandas as pd
import os
from datetime import datetime
import yfinance as yf # Though not used in the core logic yet, good for future price updates
import logging
import numpy as np # For NaN

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Path Constants ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_BASE_DIR = os.path.dirname(SCRIPT_DIR)
TRACKING_DIR = os.path.join(PROJECT_BASE_DIR, 'tracking')
TRADES_FILE_PATH = os.path.join(TRACKING_DIR, 'trades.csv')

CSV_HEADER = [
    'trade_id', 'symbol', 'entry_date', 'entry_price', 'stop_loss_price', 
    'target_price', 'risk_reward_ratio', 'atr_at_entry', 'trade_type', 
    'source_signal_date', 'status', 'current_price', 'unrealized_pnl', 
    'exit_date', 'exit_price', 'realized_pnl', 'exit_reason', 
    'holding_period', 'notes'
]

# Typing for clarity, can be removed if causing issues with older Pythons
from typing import Optional 

def _ensure_tracking_dir_exists():
    """Ensures the tracking directory exists."""
    if not os.path.exists(TRACKING_DIR):
        try:
            os.makedirs(TRACKING_DIR)
            logger.info(f"Created tracking directory: {TRACKING_DIR}")
        except OSError as e:
            logger.error(f"Error creating tracking directory {TRACKING_DIR}: {e}")
            raise # Reraise the exception as this is critical

def _get_trades_df_and_ensure_header() -> pd.DataFrame:
    """
    Reads the trades.csv file. If it doesn't exist or is empty,
    it initializes it with the correct header.
    """
    _ensure_tracking_dir_exists() # Make sure directory is there first
    try:
        if os.path.exists(TRADES_FILE_PATH) and os.path.getsize(TRADES_FILE_PATH) > 0:
            df = pd.read_csv(TRADES_FILE_PATH)
            # Basic check for header, could be more robust
            if not all(col in df.columns for col in CSV_HEADER):
                logger.warning(f"Trades file {TRADES_FILE_PATH} has missing columns. Re-initializing with full header.")
                df = pd.DataFrame(columns=CSV_HEADER)
                df.to_csv(TRADES_FILE_PATH, index=False) # Save empty df with header
        else:
            logger.info(f"Trades file {TRADES_FILE_PATH} not found or empty. Initializing with header.")
            df = pd.DataFrame(columns=CSV_HEADER)
            df.to_csv(TRADES_FILE_PATH, index=False) # Create file with header
        return df
    except pd.errors.EmptyDataError: # Handles case where file exists but is truly empty or malformed
        logger.warning(f"Pandas EmptyDataError for {TRADES_FILE_PATH}. Re-initializing with header.")
        df = pd.DataFrame(columns=CSV_HEADER)
        df.to_csv(TRADES_FILE_PATH, index=False)
        return df
    except Exception as e:
        logger.error(f"Error reading or initializing trades.csv: {e}")
        # Fallback to an empty DataFrame in memory if read fails catastrophically, 
        # but don't save it automatically here, let append attempt it.
        return pd.DataFrame(columns=CSV_HEADER)


def generate_trade_id() -> str:
    """
    Generates a unique trade ID using the current timestamp.
    """
    return datetime.now().strftime('%Y%m%d%H%M%S%f')

def add_tracked_signal(signal_data: dict) -> Optional[str]:
    """
    Adds a new trade to tracking from a signal dictionary.

    Args:
        signal_data (dict): Dictionary containing signal details. Expected keys:
                            'symbol', 'entry_price', 'stop_loss_price', 
                            'target_price', 'risk_reward_ratio', 'atr', 'date'.

    Returns:
        Optional[str]: The trade_id if successful, None otherwise.
    """
    try:
        df = _get_trades_df_and_ensure_header()
        
        trade_id = generate_trade_id()
        
        new_row = {
            'trade_id': trade_id,
            'symbol': signal_data.get('symbol'),
            'entry_date': datetime.now().date().isoformat(), # Today's date as YYYY-MM-DD
            'entry_price': signal_data.get('entry_price'),
            'stop_loss_price': signal_data.get('stop_loss_price'),
            'target_price': signal_data.get('target_price'),
            'risk_reward_ratio': signal_data.get('risk_reward_ratio'),
            'atr_at_entry': signal_data.get('atr'), # Assuming 'atr' key from signal_data
            'trade_type': 'Tracked Signal',
            'source_signal_date': signal_data.get('date'), # Assuming 'date' key
            'status': 'Active',
            'current_price': np.nan,
            'unrealized_pnl': np.nan,
            'exit_date': np.nan,
            'exit_price': np.nan,
            'realized_pnl': np.nan,
            'exit_reason': '',
            'holding_period': np.nan,
            'notes': signal_data.get('notes', '') # Optional notes from signal
        }
        
        # Validate essential signal_data keys
        required_keys = ['symbol', 'entry_price', 'stop_loss_price', 'target_price', 'date']
        if not all(key in signal_data and signal_data[key] is not None for key in required_keys):
            logger.error(f"Missing essential data in signal_data for trade {trade_id}. Required: {required_keys}")
            return None

        new_row_df = pd.DataFrame([new_row])
        df = pd.concat([df, new_row_df], ignore_index=True)
        
        df.to_csv(TRADES_FILE_PATH, index=False)
        logger.info(f"Successfully added tracked signal {trade_id} for {signal_data.get('symbol')} to {TRADES_FILE_PATH}")
        return trade_id
    except Exception as e:
        logger.error(f"Error adding tracked signal: {e}")
        return None

def add_manual_historical_pick(symbol: str, entry_price: float, stop_loss_price: float, target_price: float, notes: str = "") -> Optional[str]:
    """
    Adds a new trade based on a manual historical pick.

    Args:
        symbol (str): The stock symbol.
        entry_price (float): The entry price.
        stop_loss_price (float): The stop-loss price.
        target_price (float): The target price.
        notes (str, optional): Any notes for this trade. Defaults to "".

    Returns:
        Optional[str]: The trade_id if successful, None otherwise.
    """
    try:
        df = _get_trades_df_and_ensure_header()
        
        trade_id = generate_trade_id()
        
        calculated_rr_ratio = np.nan
        if entry_price and target_price and stop_loss_price:
            denominator = entry_price - stop_loss_price
            if denominator > 1e-9: # Avoid division by zero or tiny numbers
                calculated_rr_ratio = (target_price - entry_price) / denominator
            else:
                logger.warning(f"Could not calculate R:R for {symbol} due to zero or near-zero risk per share.")

        new_row = {
            'trade_id': trade_id,
            'symbol': symbol,
            'entry_date': datetime.now().date().isoformat(),
            'entry_price': entry_price,
            'stop_loss_price': stop_loss_price,
            'target_price': target_price,
            'risk_reward_ratio': calculated_rr_ratio,
            'atr_at_entry': np.nan, # Not typically available for manual historical
            'trade_type': 'Manual Historical Pick',
            'source_signal_date': np.nan, # Not applicable
            'status': 'Active',
            'current_price': np.nan,
            'unrealized_pnl': np.nan,
            'exit_date': np.nan,
            'exit_price': np.nan,
            'realized_pnl': np.nan,
            'exit_reason': '',
            'holding_period': np.nan,
            'notes': notes
        }
        
        new_row_df = pd.DataFrame([new_row])
        df = pd.concat([df, new_row_df], ignore_index=True)
        
        df.to_csv(TRADES_FILE_PATH, index=False)
        logger.info(f"Successfully added manual historical pick {trade_id} for {symbol} to {TRADES_FILE_PATH}")
        return trade_id
    except Exception as e:
        logger.error(f"Error adding manual historical pick: {e}")
        return None

# Make sure yfinance is imported, already done at the top.
# from datetime import datetime # Already imported
# import numpy as np # Already imported

def update_active_trades() -> bool:
    """
    Updates current_price, unrealized_pnl, and holding_period for active trades.
    Fetches current market prices using yfinance.

    Returns:
        bool: True if updates were attempted (even if some symbols failed),
              False if a critical error occurred (e.g., cannot read/write CSV).
    """
    try:
        df = _get_trades_df_and_ensure_header()
        if df.empty:
            logger.info("Trades DataFrame is empty. No trades to update.")
            return True

        active_trades_mask = df['status'] == 'Active'
        active_trade_indices = df[active_trades_mask].index

        if active_trade_indices.empty:
            logger.info("No active trades found to update.")
            return True

        logger.info(f"Found {len(active_trade_indices)} active trades to update.")
        trades_updated_count = 0

        for index in active_trade_indices:
            symbol = df.loc[index, 'symbol']
            entry_price_str = df.loc[index, 'entry_price'] # Keep as string for robust conversion
            entry_date_str = df.loc[index, 'entry_date']
            
            current_price = np.nan # Default to NaN

            try:
                logger.debug(f"Fetching current price for active trade: {symbol}")
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='2d') # Fetch 2 days to be safer with .iloc[-1]
                if not hist.empty and 'Close' in hist.columns:
                    current_price = hist['Close'].iloc[-1]
                    df.loc[index, 'current_price'] = current_price
                    logger.debug(f"Successfully fetched current price for {symbol}: {current_price}")
                    trades_updated_count +=1
                else:
                    logger.warning(f"No 'Close' price data returned for {symbol}. Skipping price update.")
                    # df.loc[index, 'current_price'] = np.nan # Ensure it is NaN if fetch fails
            except IndexError:
                 logger.warning(f"IndexError fetching price for {symbol}. Likely no data or not enough data. Skipping price update.")
            except Exception as e:
                logger.error(f"Error fetching yfinance data for {symbol}: {e}. Skipping price update for this symbol.")
                # df.loc[index, 'current_price'] = np.nan # Ensure it is NaN if fetch fails

            # Calculate Unrealized P&L (as percentage)
            # Ensure entry_price is float for calculation
            entry_price = pd.to_numeric(entry_price_str, errors='coerce')

            if pd.notna(current_price) and pd.notna(entry_price) and entry_price != 0:
                unrealized_pnl_pct = ((current_price - entry_price) / entry_price) * 100
                df.loc[index, 'unrealized_pnl'] = round(unrealized_pnl_pct, 2) # Store as percentage
            else:
                if entry_price == 0:
                    logger.warning(f"Entry price for {symbol} is 0. Cannot calculate P&L.")
                elif pd.isna(entry_price):
                     logger.warning(f"Entry price for {symbol} ('{entry_price_str}') is NaN or not numeric. Cannot calculate P&L.")
                # df.loc[index, 'unrealized_pnl'] = np.nan # Ensure it is NaN if calculation not possible

            # Calculate Holding Period
            if pd.notna(entry_date_str):
                try:
                    # Attempt to convert entry_date_str, handling potential mixed formats or NaT
                    entry_date_obj = None
                    if isinstance(entry_date_str, str):
                        entry_date_obj = datetime.strptime(entry_date_str, '%Y-%m-%d').date()
                    elif isinstance(entry_date_str, pd.Timestamp): # if already a Timestamp
                        entry_date_obj = entry_date_str.date()
                    elif isinstance(entry_date_str, datetime): # if already a datetime object
                        entry_date_obj = entry_date_str.date()
                    else: # Fallback or if it's some other type like NaT
                        logger.warning(f"Unparseable entry_date type '{type(entry_date_str)}' for {symbol} ('{entry_date_str}'). Holding period not updated.")
                    
                    if entry_date_obj:
                        holding_period_days = (datetime.now().date() - entry_date_obj).days
                        df.loc[index, 'holding_period'] = holding_period_days
                except ValueError: # Specific error for strptime
                    logger.warning(f"Could not parse entry_date string '{entry_date_str}' for {symbol}. Holding period not updated.")
                except TypeError as te: # Handles cases like NaT not having strptime, or other type issues
                     logger.warning(f"TypeError parsing entry_date '{entry_date_str}' for {symbol}: {te}. Holding period not updated.")
            else:
                # df.loc[index, 'holding_period'] = np.nan # Ensure it is NaN if entry_date is missing
                logger.warning(f"Entry_date is missing for {symbol}. Holding period not updated.")


        df.to_csv(TRADES_FILE_PATH, index=False)
        logger.info(f"Attempted to update {len(active_trade_indices)} active trades. Successfully fetched prices for {trades_updated_count} symbols.")
        return True

    except Exception as e:
        logger.error(f"Critical error in update_active_trades: {e}")
        return False

if __name__ == "__main__":
    logger.info("--- Starting Tracking Manager Demonstration ---")

    # Ensure the tracking directory and file exist for the demo
    _get_trades_df_and_ensure_header() # Create trade.csv if it doesn't exist

    sample_signal_trade_id = None # To store trade_id for later closing

    # 1. Demonstrate add_tracked_signal
    print("\nAttempting to add a tracked signal...")
    sample_signal = {
        'symbol': 'AAPL', 
        'entry_price': 170.50, 
        'stop_loss_price': 168.00, 
        'target_price': 175.50, 
        'risk_reward_ratio': (175.50 - 170.50) / (170.50 - 168.00) if (170.50 - 168.00) > 0 else np.nan, 
        'atr': 2.15, 
        'date': (datetime.now() - pd.Timedelta(days=1)).date().isoformat(), # Yesterday's date
        'notes': 'Based on strong daily candle'
    }
    trade_id_aapl = add_tracked_signal(sample_signal)
    if trade_id_aapl:
        print(f"Tracked signal for {sample_signal['symbol']} added successfully with ID: {trade_id_aapl}.")
        sample_signal_trade_id = trade_id_aapl # Save this ID for closing later
    else:
        print(f"Failed to add tracked signal for {sample_signal['symbol']}.")

    # 2. Demonstrate add_manual_historical_pick
    print("\nAttempting to add a manual historical pick...")
    trade_id_msft = add_manual_historical_pick(
        symbol='MSFT', 
        entry_price=300.00, 
        stop_loss_price=295.00, 
        target_price=310.00, 
        notes="Strong historical performance for Q1 breakouts"
    )
    if trade_id_msft:
        print(f"Manual historical pick for MSFT added successfully with ID: {trade_id_msft}.")
    else:
        print("Failed to add manual historical pick for MSFT.")
    
    # 3. Demonstrate adding another tracked signal for variety
    print("\nAttempting to add another tracked signal...")
    another_signal = {
        'symbol': 'GOOGL', 
        'entry_price': 2700.00, 
        'stop_loss_price': 2650.00, 
        'target_price': 2800.00, 
        'risk_reward_ratio': (2800.00-2700.00)/(2700.00-2650.00) if (2700.00-2650.00) > 0 else np.nan,
        'atr': 55.0, 
        'date': datetime.now().date().isoformat(), # Today's date
        'notes': 'AI news catalyst'
    }
    trade_id_googl = add_tracked_signal(another_signal)
    if trade_id_googl:
        print(f"Tracked signal for {another_signal['symbol']} added successfully with ID: {trade_id_googl}.")
    else:
        print(f"Failed to add tracked signal for {another_signal['symbol']}.")

    # 4. (Optional) Print contents of trades.csv before update
    print(f"\n--- Contents of {TRADES_FILE_PATH} before update ---")
    try:
        if os.path.exists(TRADES_FILE_PATH):
            current_trades_df = pd.read_csv(TRADES_FILE_PATH)
            if current_trades_df.empty:
                print("The trades file is empty.")
            else:
                print(current_trades_df.to_string())
        else:
            print(f"{TRADES_FILE_PATH} does not exist yet (should have been created if additions were successful).")
    except Exception as e:
        print(f"Error reading trades.csv for display: {e}")
        
    # 5. Demonstrate update_active_trades
    print("\nAttempting to update active trades...")
    if update_active_trades():
        print("Active trades updated successfully.")
    else:
        print("Failed to update active trades.")
    
    # Print contents after update
    print(f"\n--- Contents of {TRADES_FILE_PATH} after update ---")
    try:
        if os.path.exists(TRADES_FILE_PATH):
            df_after_update = pd.read_csv(TRADES_FILE_PATH)
            print(df_after_update.to_string() if not df_after_update.empty else "Trades file is empty.")
        else:
            print(f"{TRADES_FILE_PATH} does not exist.")
    except Exception as e:
        print(f"Error reading {TRADES_FILE_PATH}: {e}")

    # 6. Demonstrate close_trade
    print("\nAttempting to close a trade...")
    if sample_signal_trade_id: # If we have a trade_id from adding AAPL
        exit_price_aapl = 172.80 # Example exit price
        exit_reason_aapl = "Target hit (demo)"
        if close_trade(sample_signal_trade_id, exit_price_aapl, exit_reason_aapl):
            print(f"Trade {sample_signal_trade_id} (AAPL) closed successfully.")
        else:
            print(f"Failed to close trade {sample_signal_trade_id} (AAPL).")
    else:
        print("No trade_id captured for AAPL signal, skipping close_trade demonstration for it.")
        # As a fallback, try to find *any* active trade to close if AAPL ID wasn't captured
        try:
            df_for_closing = _get_trades_df_and_ensure_header()
            active_fallback_trades = df_for_closing[df_for_closing['status'] == 'Active']
            if not active_fallback_trades.empty:
                fallback_trade_id = active_fallback_trades['trade_id'].iloc[0]
                fallback_symbol = active_fallback_trades['symbol'].iloc[0]
                fallback_entry_price = pd.to_numeric(active_fallback_trades['entry_price'].iloc[0], errors='coerce')
                fallback_exit_price = fallback_entry_price * 1.05 if pd.notna(fallback_entry_price) else 100.0 # Dummy exit
                
                print(f"Fallback: Attempting to close trade {fallback_trade_id} ({fallback_symbol})")
                if close_trade(fallback_trade_id, fallback_exit_price, "Fallback close demo"):
                    print(f"Trade {fallback_trade_id} ({fallback_symbol}) closed successfully via fallback.")
                else:
                    print(f"Failed to close trade {fallback_trade_id} ({fallback_symbol}) via fallback.")
            else:
                print("No active trades found in CSV for fallback close demonstration.")
        except Exception as e:
            print(f"Error during fallback close demonstration: {e}")


    # Final print of trades.csv
    print(f"\n--- Final contents of {TRADES_FILE_PATH} ---")
    try:
        if os.path.exists(TRADES_FILE_PATH):
            final_trades_df = pd.read_csv(TRADES_FILE_PATH)
            print(final_trades_df.to_string() if not final_trades_df.empty else "Trades file is empty.")
        else:
            print(f"{TRADES_FILE_PATH} does not exist.")
    except Exception as e:
        print(f"Error reading {TRADES_FILE_PATH}: {e}")
        
    logger.info("--- Tracking Manager Demonstration Finished ---")
