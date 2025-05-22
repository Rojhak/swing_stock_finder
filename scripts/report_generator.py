import pandas as pd
from datetime import datetime
import os
import numpy as np
import logging
from pprint import pprint
from typing import Dict, List, Optional, Any # For type hinting

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

def _safe_division(numerator: float, denominator: float, default_val: float = 0.0) -> float:
    """Safely divides two numbers, returning default_val if denominator is zero."""
    if denominator == 0:
        return default_val
    return numerator / denominator

def _calculate_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculates performance metrics for a given DataFrame of closed trades.
    Assumes df contains only closed trades for the desired period and type.
    """
    metrics: Dict[str, Any] = {
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'win_rate': 0.0,
        'total_pnl': 0.0, # Assuming realized_pnl is a numerical value (e.g., percentage or currency)
        'avg_win_pnl': 0.0,
        'avg_loss_pnl': 0.0,
        'profit_factor': 0.0,
        'sum_positive_pnl': 0.0,
        'sum_negative_pnl': 0.0,
    }

    if df.empty:
        return metrics

    # Ensure 'realized_pnl' is numeric, coercing errors to NaN
    df['realized_pnl'] = pd.to_numeric(df['realized_pnl'], errors='coerce')
    
    # Drop rows where 'realized_pnl' became NaN after coercion, as they can't be used in calculations
    df_cleaned = df.dropna(subset=['realized_pnl'])
    if len(df_cleaned) != len(df):
        logger.warning(f"Dropped {len(df) - len(df_cleaned)} rows due to non-numeric 'realized_pnl'.")

    if df_cleaned.empty: # If all rows were dropped
        return metrics

    metrics['total_trades'] = len(df_cleaned)
    
    winning_trades_df = df_cleaned[df_cleaned['realized_pnl'] > 0]
    losing_trades_df = df_cleaned[df_cleaned['realized_pnl'] <= 0] # Includes zero PnL as losing/breakeven

    metrics['winning_trades'] = len(winning_trades_df)
    metrics['losing_trades'] = len(losing_trades_df)
    
    metrics['win_rate'] = _safe_division(metrics['winning_trades'], metrics['total_trades']) * 100
    
    metrics['total_pnl'] = df_cleaned['realized_pnl'].sum()
    
    metrics['sum_positive_pnl'] = winning_trades_df['realized_pnl'].sum()
    metrics['sum_negative_pnl'] = losing_trades_df['realized_pnl'].sum() # This will be <= 0

    metrics['avg_win_pnl'] = _safe_division(metrics['sum_positive_pnl'], metrics['winning_trades'])
    metrics['avg_loss_pnl'] = _safe_division(metrics['sum_negative_pnl'], metrics['losing_trades'])
    
    metrics['profit_factor'] = _safe_division(metrics['sum_positive_pnl'], abs(metrics['sum_negative_pnl']))
    
    return metrics

def get_monthly_performance_report(year: int, month: int) -> Dict[str, Any]:
    """
    Generates a monthly performance report from trades in trades.csv.

    Args:
        year (int): The year for the report.
        month (int): The month (1-12) for the report.

    Returns:
        dict: A dictionary containing performance statistics for the month.
    """
    report: Dict[str, Any] = {
        'report_month_year': f"{month:02d}-{year}",
        'combined': {},
        'tracked_signal': {},
        'manual_historical_pick': {},
        'contributing_trades': [],
        'notes': ""
    }

    if not os.path.exists(TRADES_FILE_PATH) or os.path.getsize(TRADES_FILE_PATH) == 0:
        logger.warning(f"Trades file not found or empty: {TRADES_FILE_PATH}")
        report['notes'] = "Trades file not found or empty."
        # Initialize metric dicts to avoid KeyError later
        report['combined'] = _calculate_metrics(pd.DataFrame())
        report['tracked_signal'] = _calculate_metrics(pd.DataFrame())
        report['manual_historical_pick'] = _calculate_metrics(pd.DataFrame())
        return report

    try:
        df = pd.read_csv(TRADES_FILE_PATH)
    except Exception as e:
        logger.error(f"Error reading trades CSV {TRADES_FILE_PATH}: {e}")
        report['notes'] = f"Error reading trades CSV: {e}"
        report['combined'] = _calculate_metrics(pd.DataFrame())
        report['tracked_signal'] = _calculate_metrics(pd.DataFrame())
        report['manual_historical_pick'] = _calculate_metrics(pd.DataFrame())
        return report

    if df.empty:
        report['notes'] = "No trades found in the CSV file."
        report['combined'] = _calculate_metrics(pd.DataFrame())
        report['tracked_signal'] = _calculate_metrics(pd.DataFrame())
        report['manual_historical_pick'] = _calculate_metrics(pd.DataFrame())
        return report

    # Convert 'exit_date' to datetime objects, coercing errors to NaT
    # Ensure 'status' column exists
    if 'exit_date' not in df.columns or 'status' not in df.columns:
        logger.error("Trades CSV is missing 'exit_date' or 'status' column.")
        report['notes'] = "Trades CSV is missing 'exit_date' or 'status' column."
        report['combined'] = _calculate_metrics(pd.DataFrame())
        report['tracked_signal'] = _calculate_metrics(pd.DataFrame())
        report['manual_historical_pick'] = _calculate_metrics(pd.DataFrame())
        return report

    df['exit_date'] = pd.to_datetime(df['exit_date'], errors='coerce')

    # Filter for closed trades within the specified month and year
    closed_trades_month_df = df[
        (df['status'] == 'Closed') &
        (df['exit_date'].dt.year == year) &
        (df['exit_date'].dt.month == month)
    ].copy() # Use .copy() to avoid SettingWithCopyWarning

    if closed_trades_month_df.empty:
        report['notes'] = f"No closed trades found for {month:02d}-{year}."
        # Still run _calculate_metrics with empty DF to get zeroed structure
        report['combined'] = _calculate_metrics(pd.DataFrame())
        report['tracked_signal'] = _calculate_metrics(pd.DataFrame())
        report['manual_historical_pick'] = _calculate_metrics(pd.DataFrame())
        return report

    # Calculate metrics for combined trades
    report['combined'] = _calculate_metrics(closed_trades_month_df.copy()) # Pass copy

    # Filter and calculate for 'Tracked Signal'
    tracked_signals_df = closed_trades_month_df[
        closed_trades_month_df['trade_type'] == 'Tracked Signal'
    ].copy()
    report['tracked_signal'] = _calculate_metrics(tracked_signals_df)

    # Filter and calculate for 'Manual Historical Pick'
    manual_picks_df = closed_trades_month_df[
        closed_trades_month_df['trade_type'] == 'Manual Historical Pick'
    ].copy()
    report['manual_historical_pick'] = _calculate_metrics(manual_picks_df)
    
    # List of contributing trades
    # Ensure 'realized_pnl' is numeric for display, using the cleaned version if possible
    closed_trades_month_df['realized_pnl_numeric'] = pd.to_numeric(closed_trades_month_df['realized_pnl'], errors='coerce')
    
    report['contributing_trades'] = closed_trades_month_df[
        ['trade_id', 'symbol', 'realized_pnl_numeric', 'trade_type', 'exit_date']
    ].rename(columns={'realized_pnl_numeric': 'realized_pnl'}).to_dict(orient='records')
    
    if not report['notes']: # If no prior notes, confirm report generation
        report['notes'] = f"Report generated successfully for {month:02d}-{year}."

    return report

if __name__ == "__main__":
    logger.info("--- Generating Monthly Performance Report Demonstration ---")
    
    # Example: Generate report for the current month and year
    # You might want to create some dummy data in tracking/trades.csv using tracking_manager.py's demo
    # for this report to show meaningful data.
    
    current_datetime = datetime.now()
    report_year = current_datetime.year
    report_month = current_datetime.month 
    
    # To test with specific data, you might run tracking_manager.py's demo,
    # then manually close some trades by editing trades.csv or using close_trade,
    # then run this for that month.
    # For example, if tracking_manager creates trades on 2023-10-25 and you close them on 2023-10-26:
    # report_year = 2023
    # report_month = 10 
    # (Adjust if your system date is different)

    print(f"\nRequesting report for: {report_month:02d}-{report_year}")
    monthly_report = get_monthly_performance_report(report_year, report_month)
    
    print("\n--- Monthly Performance Report ---")
    pprint(monthly_report)
    
    # Example of how to generate a report for a different month if needed for testing:
    # print("\nRequesting report for: 01-2024") # Assuming you might have test data there
    # monthly_report_jan_2024 = get_monthly_performance_report(2024, 1)
    # print("\n--- Monthly Performance Report (01-2024) ---")
    # pprint(monthly_report_jan_2024)

    logger.info("\n--- Attempting to Export Trade History ---")
    output_dir_demo = os.path.join(PROJECT_BASE_DIR, 'reports_output')
    
    trade_history_path = export_trade_history(output_dir_demo)
    if trade_history_path:
        logger.info(f"Trade history exported successfully to: {trade_history_path}")
    else:
        logger.error("Failed to export trade history.")

    logger.info("\n--- Attempting to Export Monthly Performance CSV ---")
    monthly_report_csv_path = export_monthly_report_csv(report_year, report_month, output_dir_demo)
    if monthly_report_csv_path:
        logger.info(f"Monthly performance report CSV exported successfully to: {monthly_report_csv_path}")
    else:
        logger.error("Failed to export monthly performance report CSV.")

    logger.info("--- Report Generation Demonstration Finished ---")
