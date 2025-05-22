import unittest
import pandas as pd
import os
import numpy as np
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock, call

# Assuming tests are run from the project root directory
from scripts.tracking_manager import (
    add_tracked_signal,
    add_manual_historical_pick,
    update_active_trades,
    close_trade,
    generate_trade_id,
    TRADES_FILE_PATH,
    CSV_HEADER,
    _get_trades_df_and_ensure_header, # For setup/teardown utility
    _ensure_tracking_dir_exists # To ensure tracking dir is there for _get_trades_df...
)
import scripts.tracking_manager as tracking_manager_module # For patching yf.Ticker

# Disable logging for tests unless specifically testing for log messages
import logging
logging.disable(logging.CRITICAL)

class TestTrackingManager(unittest.TestCase):

    def setUp(self):
        """Set up a clean environment for each test."""
        self.test_csv_path = TRADES_FILE_PATH
        # Ensure tracking directory exists for _get_trades_df_and_ensure_header
        # This is implicitly handled by _get_trades_df_and_ensure_header's call to _ensure_tracking_dir_exists
        
        # Clean up any existing file to ensure a fresh state
        if os.path.exists(self.test_csv_path):
            os.remove(self.test_csv_path)
        
        # Initialize a fresh CSV file with headers
        _get_trades_df_and_ensure_header()

    def tearDown(self):
        """Clean up after each test."""
        if os.path.exists(self.test_csv_path):
            os.remove(self.test_csv_path)
        # Attempt to remove the tracking directory if it's empty - be careful with this in real scenarios
        tracking_dir = os.path.dirname(self.test_csv_path)
        if os.path.exists(tracking_dir) and not os.listdir(tracking_dir):
            try:
                os.rmdir(tracking_dir)
            except OSError: 
                pass # Ignore if it fails (e.g. not empty, though it should be)


    # 3. Test generate_trade_id
    def test_generate_trade_id_format(self):
        trade_id = generate_trade_id()
        self.assertIsInstance(trade_id, str)
        self.assertTrue(len(trade_id) > 10) # Timestamps are usually longer
        self.assertTrue(trade_id.isdigit()) # Expecting YYYYMMDDHHMMSSffffff
        try:
            datetime.strptime(trade_id, '%Y%m%d%H%M%S%f')
        except ValueError:
            self.fail("generate_trade_id did not produce a parseable timestamp string.")

    def test_generate_trade_id_uniqueness(self):
        # Generate a few IDs in quick succession
        ids = {generate_trade_id() for _ in range(5)}
        self.assertEqual(len(ids), 5, "Generated trade IDs are not unique.")

    # 4. Test add_tracked_signal
    def test_add_tracked_signal_success(self):
        sample_signal_data = {
            'symbol': 'TEST', 'entry_price': 100.0, 'stop_loss_price': 90.0,
            'target_price': 120.0, 'risk_reward_ratio': 2.0, 'atr': 5.0,
            'date': (datetime.now() - timedelta(days=1)).date().isoformat(), # Source signal date
            'notes': 'Test signal'
        }
        trade_id = add_tracked_signal(sample_signal_data)
        self.assertIsInstance(trade_id, str)

        df = pd.read_csv(self.test_csv_path)
        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row['symbol'], sample_signal_data['symbol'])
        self.assertEqual(row['entry_price'], sample_signal_data['entry_price'])
        self.assertEqual(row['stop_loss_price'], sample_signal_data['stop_loss_price'])
        self.assertEqual(row['target_price'], sample_signal_data['target_price'])
        self.assertEqual(row['risk_reward_ratio'], sample_signal_data['risk_reward_ratio'])
        self.assertEqual(row['atr_at_entry'], sample_signal_data['atr'])
        self.assertEqual(row['source_signal_date'], sample_signal_data['date'])
        self.assertEqual(row['notes'], sample_signal_data['notes'])
        self.assertEqual(row['status'], 'Active')
        self.assertEqual(row['trade_type'], 'Tracked Signal')
        self.assertEqual(row['entry_date'], datetime.now().date().isoformat()) # Today's date

    def test_add_tracked_signal_missing_data(self):
        incomplete_data = {'symbol': 'FAIL'} # Missing many required fields
        trade_id = add_tracked_signal(incomplete_data)
        self.assertIsNone(trade_id)
        df = pd.read_csv(self.test_csv_path)
        self.assertTrue(df.empty, "CSV should be empty after failed add.")

    # 5. Test add_manual_historical_pick
    def test_add_manual_pick_success(self):
        trade_id = add_manual_historical_pick('MANUAL', 200.0, 180.0, 240.0, "Manual test")
        self.assertIsInstance(trade_id, str)
        df = pd.read_csv(self.test_csv_path)
        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row['symbol'], 'MANUAL')
        self.assertEqual(row['entry_price'], 200.0)
        self.assertEqual(row['trade_type'], 'Manual Historical Pick')
        self.assertEqual(row['status'], 'Active')
        self.assertEqual(row['notes'], "Manual test")
        self.assertAlmostEqual(row['risk_reward_ratio'], (240.0 - 200.0) / (200.0 - 180.0))

    def test_add_manual_pick_rr_calculation(self):
        # Test R:R calculation
        add_manual_historical_pick('RR_TEST', 100.0, 90.0, 120.0) # Expected R:R = (120-100)/(100-90) = 20/10 = 2.0
        df = pd.read_csv(self.test_csv_path)
        self.assertAlmostEqual(df.iloc[0]['risk_reward_ratio'], 2.0)
        
        # Test R:R with zero denominator (entry_price == stop_loss_price)
        os.remove(self.test_csv_path) # Clean for next part of test
        _get_trades_df_and_ensure_header()
        add_manual_historical_pick('RR_ZERO_DENOM', 100.0, 100.0, 120.0)
        df_zero_denom = pd.read_csv(self.test_csv_path)
        self.assertTrue(pd.isna(df_zero_denom.iloc[0]['risk_reward_ratio']))
        
    # 6. Test update_active_trades
    @patch('scripts.tracking_manager.yf.Ticker')
    def test_update_active_trades_success(self, mock_yfinance_ticker):
        # Setup mock yf.Ticker response
        mock_ticker_instance = MagicMock()
        mock_history_df = pd.DataFrame({'Close': [105.0, 108.0]}, index=[datetime.now() - timedelta(days=1), datetime.now()])
        mock_ticker_instance.history.return_value = mock_history_df
        mock_yfinance_ticker.return_value = mock_ticker_instance

        # Add an active trade
        entry_date_str = (datetime.now() - timedelta(days=5)).date().isoformat()
        signal_data = {
            'symbol': 'UPDT', 'entry_price': 100.0, 'stop_loss_price': 90.0,
            'target_price': 120.0, 'risk_reward_ratio': 2.0, 'atr': 5.0,
            'date': entry_date_str, 'notes': 'Update test'
        }
        add_tracked_signal(signal_data) # This sets entry_date to today, let's adjust it post-add for holding period test
        
        # Manually adjust entry_date in CSV for a more realistic holding period test
        df_temp = pd.read_csv(self.test_csv_path)
        df_temp.loc[0, 'entry_date'] = entry_date_str 
        df_temp.to_csv(self.test_csv_path, index=False)

        result = update_active_trades()
        self.assertTrue(result)

        df = pd.read_csv(self.test_csv_path)
        row = df.iloc[0]
        self.assertEqual(row['current_price'], 108.0)
        expected_pnl = ((108.0 - 100.0) / 100.0) * 100
        self.assertAlmostEqual(row['unrealized_pnl'], expected_pnl)
        
        # Holding period calculation
        expected_holding_period = (datetime.now().date() - datetime.strptime(entry_date_str, '%Y-%m-%d').date()).days
        self.assertEqual(row['holding_period'], expected_holding_period)


    def test_update_active_trades_no_active_trades(self):
        # Ensure CSV is empty or has only closed trades
        add_manual_historical_pick('CLOSED_MANUAL', 100, 90, 110)
        df = pd.read_csv(self.test_csv_path)
        df.loc[0, 'status'] = 'Closed'
        df.to_csv(self.test_csv_path, index=False)

        result = update_active_trades()
        self.assertTrue(result)
        # Could check that logger.info("No active trades found...") was called if we mock logger

    @patch('scripts.tracking_manager.yf.Ticker')
    def test_update_active_trades_yfinance_error(self, mock_yfinance_ticker):
        mock_yfinance_ticker.side_effect = Exception("yfinance API error")

        add_tracked_signal({
            'symbol': 'YF_ERR', 'entry_price': 100.0, 'stop_loss_price': 90.0,
            'target_price': 120.0, 'risk_reward_ratio': 2.0, 'atr': 5.0,
            'date': (datetime.now() - timedelta(days=1)).date().isoformat()
        })
        
        result = update_active_trades()
        self.assertTrue(result) # Function should still complete "successfully" overall
        df = pd.read_csv(self.test_csv_path)
        row = df.iloc[0]
        self.assertTrue(pd.isna(row['current_price']))
        self.assertTrue(pd.isna(row['unrealized_pnl']))

    # 7. Test close_trade
    def test_close_trade_success(self):
        signal_data = {
            'symbol': 'CLOSESUCCESS', 'entry_price': 100.0, 'stop_loss_price': 90.0,
            'target_price': 120.0, 'risk_reward_ratio': 2.0, 'atr': 5.0,
            'date': (datetime.now() - timedelta(days=1)).date().isoformat()
        }
        trade_id = add_tracked_signal(signal_data)
        self.assertIsNotNone(trade_id)

        exit_price = 115.0
        exit_reason = "Target almost hit"
        result = close_trade(trade_id, exit_price, exit_reason)
        self.assertTrue(result)

        df = pd.read_csv(self.test_csv_path)
        row = df[df['trade_id'] == trade_id].iloc[0]
        self.assertEqual(row['status'], 'Closed')
        self.assertEqual(row['exit_price'], exit_price)
        self.assertEqual(row['exit_date'], datetime.now().date().isoformat())
        self.assertEqual(row['exit_reason'], exit_reason)
        expected_pnl = ((exit_price - 100.0) / 100.0) * 100
        self.assertAlmostEqual(row['realized_pnl'], expected_pnl)
        # Holding period will be 0 if entry_date and exit_date are the same (both today)
        # This is because add_tracked_signal sets entry_date to today.
        self.assertEqual(row['holding_period'], 0)


    def test_close_trade_already_closed(self):
        trade_id = add_tracked_signal({
            'symbol': 'ALREADYCLOSED', 'entry_price': 100.0, 'stop_loss_price': 90.0,
            'target_price': 120.0, 'risk_reward_ratio': 2.0, 'atr': 5.0,
            'date': (datetime.now() - timedelta(days=1)).date().isoformat()
        })
        self.assertTrue(close_trade(trade_id, 110.0, "Initial close"))
        
        # Try to close again
        result_second_close = close_trade(trade_id, 115.0, "Second attempt")
        self.assertTrue(result_second_close) # Should return True as per spec (already closed)

        df = pd.read_csv(self.test_csv_path)
        row = df[df['trade_id'] == trade_id].iloc[0]
        self.assertEqual(row['exit_price'], 110.0) # Should retain first exit price
        self.assertEqual(row['exit_reason'], "Initial close") # Should retain first reason

    def test_close_trade_id_not_found(self):
        result = close_trade("NONEXISTENT_ID", 100.0, "Test")
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
