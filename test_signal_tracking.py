#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Signal Tracking Test Script

This script demonstrates using auto_tracker.py with real signal data.
It tracks signals from existing files and shows performance metrics.
"""

import os
import sys
import glob
import pytest
try:
    import pandas as pd
except ModuleNotFoundError:
    pd = None
    pytest.skip("pandas not installed", allow_module_level=True)
from pathlib import Path
from datetime import datetime, timedelta
import logging
import argparse

# Add the project root to the path if needed
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

# Import the auto_tracker functionality
from auto_tracker import track_signals, find_latest_signal_file
from scripts.tracking_manager import update_active_trades, close_trade

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_tracked_trades():
    """Load current tracked trades"""
    trades_path = os.path.join(script_dir, 'tracking', 'trades.csv')
    if os.path.exists(trades_path):
        try:
            trades_df = pd.read_csv(trades_path)
            return trades_df
        except Exception as e:
            logger.error(f"Error reading trades.csv: {e}")
    
    logger.warning("No trades.csv found or file is empty")
    return pd.DataFrame()

def run_signal_tracking_test(days_history=7, track_all=False, dry_run=True):
    """
    Run a test of the auto_tracker functionality on recent signal files
    
    Args:
        days_history: Number of days of signal history to process
        track_all: Whether to track all signals or just overall signals
        dry_run: If True, don't actually track signals
    """
    logger.info(f"Starting signal tracking test with {days_history} days of history")
    logger.info(f"Track all signals: {track_all}, Dry run mode: {dry_run}")
    
    # Find all signal files within the date range
    base_path = Path(os.path.join(script_dir, "results", "live_signals"))
    json_files = glob.glob(str(base_path / "daily_signal_*.json"))
    
    if not json_files:
        logger.error("No signal JSON files found")
        return
    
    # Sort by date
    json_files = sorted(json_files)
    
    # Filter to just the last N days if requested
    if days_history > 0 and days_history < len(json_files):
        json_files = json_files[-days_history:]
    
    logger.info(f"Found {len(json_files)} signal files to process")
    
    # Process each signal file
    total_tracked = 0
    
    for signal_file in json_files:
        logger.info(f"Processing {os.path.basename(signal_file)}...")
        
        # Track signals from this file
        tracked_ids = track_signals(signal_file, track_all=track_all, dry_run=dry_run)
        
        if not dry_run:
            total_tracked += len(tracked_ids)
            logger.info(f"Tracked {len(tracked_ids)} signals from {os.path.basename(signal_file)}")
        else:
            logger.info(f"Would have tracked signals from {os.path.basename(signal_file)} (dry run)")
    
    # Show summary
    if not dry_run:
        logger.info(f"Completed signal tracking test. Tracked {total_tracked} total signals.")
        
        # Update all active trades to get current prices and P&L
        logger.info("Updating active trades with current prices...")
        update_active_trades()
        
        # Display current trade status
        trades_df = load_tracked_trades()
        if not trades_df.empty:
            active_trades = trades_df[trades_df['status'] == 'Active']
            closed_trades = trades_df[trades_df['status'] == 'Closed']
            
            logger.info(f"Current trade statistics:")
            logger.info(f"  Total trades: {len(trades_df)}")
            logger.info(f"  Active trades: {len(active_trades)}")
            logger.info(f"  Closed trades: {len(closed_trades)}")
            
            if not active_trades.empty:
                avg_unrealized_pnl = active_trades['unrealized_pnl'].mean()
                logger.info(f"  Average unrealized P&L: {avg_unrealized_pnl:.2f}%")
            
            if not closed_trades.empty:
                avg_realized_pnl = closed_trades['realized_pnl'].mean()
                logger.info(f"  Average realized P&L: {avg_realized_pnl:.2f}%")
    else:
        logger.info("Completed signal tracking test (dry run mode).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Signal Tracking Test")
    parser.add_argument("--days", type=int, default=7, help="Number of days of signal history to process")
    parser.add_argument("--track-all", action="store_true", help="Track all signals (not just overall)")
    parser.add_argument("--live", action="store_true", help="Actually track signals (not dry run)")
    
    args = parser.parse_args()
    
    run_signal_tracking_test(days_history=args.days, track_all=args.track_all, dry_run=not args.live)
