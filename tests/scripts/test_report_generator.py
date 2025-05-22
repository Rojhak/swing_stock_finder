import unittest
import pandas as pd
import os
import numpy as np
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock
from pprint import pprint # For debugging test failures if needed

# Assuming tests are run from the project root directory
from scripts.report_generator import get_monthly_performance_report, TRADES_FILE_PATH, _calculate_metrics, _safe_division
from scripts.tracking_manager import _get_trades_df_and_ensure_header, CSV_HEADER # For test setup

# Disable logging for tests unless specifically testing for log messages
import logging
logging.disable(logging.CRITICAL)

class TestReportGenerator(unittest.TestCase):

    def setUp(self):
        """Set up a clean environment for each test."""
        self.test_csv_path = TRADES_FILE_PATH
        # Ensure tracking directory exists (implicitly handled by _get_trades_df_and_ensure_header)
        
        # Clean up any existing file to ensure a fresh state
        if os.path.exists(self.test_csv_path):
            os.remove(self.test_csv_path)
        
        # Initialize a fresh CSV file with headers
        _get_trades_df_and_ensure_header()

    def tearDown(self):
        """Clean up after each test."""
        if os.path.exists(self.test_csv_path):
            os.remove(self.test_csv_path)
        tracking_dir = os.path.dirname(self.test_csv_path)
        if os.path.exists(tracking_dir) and not os.listdir(tracking_dir):
            try:
                os.rmdir(tracking_dir)
            except OSError:
                pass # Ignore if it fails

    @patch('scripts.report_generator.os.path.exists')
    def test_report_no_trades_file(self, mock_os_exists):
        """Test when the trades.csv file does not exist."""
        mock_os_exists.return_value = False
        report = get_monthly_performance_report(2023, 10)
        
        self.assertIn("Trades file not found or empty", report.get('notes', ""))
        for category in ['combined', 'tracked_signal', 'manual_historical_pick']:
            self.assertEqual(report[category].get('total_trades', -1), 0) 

    def test_report_empty_trades_file(self):
        """Test when trades.csv is empty or contains only headers."""
        # setUp already creates an empty file with headers
        report = get_monthly_performance_report(2023, 10)
        self.assertIn("No trades found in the CSV file.", report.get('notes', "")) # Adjusted based on actual notes
        for category in ['combined', 'tracked_signal', 'manual_historical_pick']:
            self.assertEqual(report[category].get('total_trades', -1), 0)

    def test_report_no_closed_trades_in_month(self):
        """Test with trades present, but none closed in the target month."""
        sample_trades = [
            {'trade_id': 'T1', 'symbol': 'AAPL', 'entry_date': '2023-10-01', 'status': 'Active', 'realized_pnl': np.nan, 'trade_type': 'Tracked Signal', 'exit_date': np.nan},
            {'trade_id': 'T2', 'symbol': 'MSFT', 'entry_date': '2023-09-05', 'status': 'Closed', 'realized_pnl': 50, 'trade_type': 'Manual Historical Pick', 'exit_date': '2023-09-20'},
        ]
        pd.DataFrame(sample_trades).to_csv(self.test_csv_path, index=False)
        
        report = get_monthly_performance_report(2023, 10) # Target month October
        self.assertIn("No closed trades found for 10-2023", report.get('notes', ""))
        self.assertEqual(report['combined'].get('total_trades', -1), 0)
        self.assertEqual(len(report.get('contributing_trades', [])), 0)

    def test_report_with_data_various_scenarios(self):
        """Comprehensive test with diverse trade data for a specific month."""
        trades_data = [
            # Trades for October 2023
            {'trade_id': 'OCT001', 'symbol': 'GOOG', 'entry_date': '2023-10-01', 'exit_date': '2023-10-05', 'status': 'Closed', 'realized_pnl': 100.0, 'trade_type': 'Tracked Signal'},
            {'trade_id': 'OCT002', 'symbol': 'MSFT', 'entry_date': '2023-10-02', 'exit_date': '2023-10-08', 'status': 'Closed', 'realized_pnl': -50.0, 'trade_type': 'Tracked Signal'},
            {'trade_id': 'OCT003', 'symbol': 'AMZN', 'entry_date': '2023-10-03', 'exit_date': '2023-10-10', 'status': 'Closed', 'realized_pnl': 0.0, 'trade_type': 'Manual Historical Pick'},
            {'trade_id': 'OCT004', 'symbol': 'TSLA', 'entry_date': '2023-10-04', 'exit_date': '2023-10-12', 'status': 'Closed', 'realized_pnl': 200.0, 'trade_type': 'Manual Historical Pick'},
            {'trade_id': 'OCT005', 'symbol': 'NVDA', 'entry_date': '2023-10-05', 'exit_date': '2023-10-15', 'status': 'Closed', 'realized_pnl': 'not_a_number', 'trade_type': 'Tracked Signal'}, # Bad P&L
            {'trade_id': 'OCT006', 'symbol': 'META', 'entry_date': '2023-10-06', 'exit_date': '2023-10-18', 'status': 'Closed', 'realized_pnl': 75.0, 'trade_type': 'Tracked Signal'},
            # Trades for other months or active
            {'trade_id': 'SEP001', 'symbol': 'NFLX', 'entry_date': '2023-09-01', 'exit_date': '2023-09-10', 'status': 'Closed', 'realized_pnl': 20.0, 'trade_type': 'Tracked Signal'},
            {'trade_id': 'NOV001', 'symbol': 'DIS', 'entry_date': '2023-10-10', 'exit_date': '2023-11-05', 'status': 'Closed', 'realized_pnl': 30.0, 'trade_type': 'Manual Historical Pick'}, # Exit in Nov
            {'trade_id': 'ACT001', 'symbol': 'CRM', 'entry_date': '2023-10-15', 'exit_date': np.nan, 'status': 'Active', 'realized_pnl': np.nan, 'trade_type': 'Tracked Signal'},
        ]
        # Add all columns to avoid issues with missing ones, fill with defaults
        full_trades_data = []
        for t in trades_data:
            row = {col: np.nan for col in CSV_HEADER} # Initialize with NaNs or defaults
            row.update(t)
            row['entry_price'] = row.get('entry_price', 100) # Default if not set
            row['stop_loss_price'] = row.get('stop_loss_price', 90)
            row['target_price'] = row.get('target_price', 110)
            full_trades_data.append(row)

        pd.DataFrame(full_trades_data).to_csv(self.test_csv_path, index=False)
        
        report = get_monthly_performance_report(2023, 10)
        
        self.assertEqual(report['report_month_year'], '10-2023')

        # --- Combined ---
        # OCT001 (100), OCT002 (-50), OCT003 (0), OCT004 (200), OCT006 (75). OCT005 is dropped.
        # Total: 5 trades. Wins: 3 (100, 200, 75). Losses: 1 (-50). Breakeven (loss by def): 1 (0)
        comb = report['combined']
        self.assertEqual(comb['total_trades'], 5)
        self.assertEqual(comb['winning_trades'], 3)
        self.assertEqual(comb['losing_trades'], 2) # OCT002, OCT003
        self.assertAlmostEqual(comb['win_rate'], (3/5)*100)
        self.assertAlmostEqual(comb['total_pnl'], 100.0 - 50.0 + 0.0 + 200.0 + 75.0) # 325.0
        self.assertAlmostEqual(comb['avg_win_pnl'], (100.0 + 200.0 + 75.0) / 3) # 375/3 = 125
        self.assertAlmostEqual(comb['avg_loss_pnl'], (-50.0 + 0.0) / 2) # -25
        self.assertAlmostEqual(comb['profit_factor'], (100.0 + 200.0 + 75.0) / abs(-50.0 + 0.0)) # 375 / 50 = 7.5

        # --- Tracked Signal ---
        # OCT001 (100), OCT002 (-50), OCT006 (75). OCT005 dropped.
        # Total: 3 trades. Wins: 2 (100, 75). Losses: 1 (-50).
        ts = report['tracked_signal']
        self.assertEqual(ts['total_trades'], 3)
        self.assertEqual(ts['winning_trades'], 2)
        self.assertEqual(ts['losing_trades'], 1)
        self.assertAlmostEqual(ts['win_rate'], (2/3)*100)
        self.assertAlmostEqual(ts['total_pnl'], 100.0 - 50.0 + 75.0) # 125.0
        self.assertAlmostEqual(ts['avg_win_pnl'], (100.0 + 75.0) / 2) # 87.5
        self.assertAlmostEqual(ts['avg_loss_pnl'], -50.0 / 1) # -50.0
        self.assertAlmostEqual(ts['profit_factor'], (100.0 + 75.0) / abs(-50.0)) # 175 / 50 = 3.5
        
        # --- Manual Historical Pick ---
        # OCT003 (0), OCT004 (200)
        # Total: 2 trades. Wins: 1 (200). Breakeven(loss): 1 (0)
        mhp = report['manual_historical_pick']
        self.assertEqual(mhp['total_trades'], 2)
        self.assertEqual(mhp['winning_trades'], 1)
        self.assertEqual(mhp['losing_trades'], 1) # OCT003 (0 PNL)
        self.assertAlmostEqual(mhp['win_rate'], (1/2)*100)
        self.assertAlmostEqual(mhp['total_pnl'], 0.0 + 200.0) # 200.0
        self.assertAlmostEqual(mhp['avg_win_pnl'], 200.0 / 1)
        self.assertAlmostEqual(mhp['avg_loss_pnl'], 0.0 / 1) # Avg loss is 0
        self.assertAlmostEqual(mhp['profit_factor'], _safe_division(200.0, abs(0.0))) # Profit factor: sum_positive / abs(sum_negative), 0 if sum_negative is 0

        # --- Contributing Trades ---
        contrib_trades = report['contributing_trades']
        self.assertEqual(len(contrib_trades), 5) # OCT001, OCT002, OCT003, OCT004, OCT006
        contrib_ids = [t['trade_id'] for t in contrib_trades]
        self.assertIn('OCT001', contrib_ids)
        self.assertNotIn('OCT005', contrib_ids) # Dropped due to bad P&L
        self.assertNotIn('SEP001', contrib_ids)
        
        # Check one trade's details
        oct001_data = next(t for t in contrib_trades if t['trade_id'] == 'OCT001')
        self.assertEqual(oct001_data['symbol'], 'GOOG')
        self.assertAlmostEqual(oct001_data['realized_pnl'], 100.0)


    def test_report_pnl_summation_edge_cases(self):
        """Test profit factor and avg P&L with only wins or only losses."""
        # Only winning trades
        win_trades = [
            {'trade_id': 'WIN001', 'symbol': 'WIN', 'exit_date': '2023-10-05', 'status': 'Closed', 'realized_pnl': 100.0, 'trade_type': 'Tracked Signal'},
            {'trade_id': 'WIN002', 'symbol': 'WIN', 'exit_date': '2023-10-08', 'status': 'Closed', 'realized_pnl': 50.0, 'trade_type': 'Tracked Signal'},
        ]
        pd.DataFrame(win_trades).to_csv(self.test_csv_path, index=False)
        report_wins = get_monthly_performance_report(2023, 10)['combined']
        self.assertAlmostEqual(report_wins['avg_win_pnl'], 75.0)
        self.assertEqual(report_wins['avg_loss_pnl'], 0.0) # No losses
        self.assertEqual(report_wins['profit_factor'], 0.0) # _safe_division default for 0 denominator (abs sum negative pnl)

        # Clean up for next sub-test
        if os.path.exists(self.test_csv_path): os.remove(self.test_csv_path)
        _get_trades_df_and_ensure_header()

        # Only losing trades
        loss_trades = [
            {'trade_id': 'LOSS001', 'symbol': 'LOSS', 'exit_date': '2023-10-05', 'status': 'Closed', 'realized_pnl': -20.0, 'trade_type': 'Tracked Signal'},
            {'trade_id': 'LOSS002', 'symbol': 'LOSS', 'exit_date': '2023-10-08', 'status': 'Closed', 'realized_pnl': -30.0, 'trade_type': 'Tracked Signal'},
        ]
        pd.DataFrame(loss_trades).to_csv(self.test_csv_path, index=False)
        report_losses = get_monthly_performance_report(2023, 10)['combined']
        self.assertEqual(report_losses['avg_win_pnl'], 0.0) # No wins
        self.assertAlmostEqual(report_losses['avg_loss_pnl'], -25.0)
        self.assertAlmostEqual(report_losses['profit_factor'], 0.0) # Sum positive pnl is 0

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
