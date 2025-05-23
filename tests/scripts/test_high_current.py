import unittest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, call, mock_open
from datetime import datetime, date, timedelta
import json
from pathlib import Path
import logging # Import logging

# Assuming tests are run from the project root directory
from scripts.high_current import find_current_setups, generate_json_output, STRATEGY_PARAMS
import scripts.high_current as high_current_module # To patch globals

# Define PROJECT_BASE_DIR for tests, assuming tests are in tests/scripts/
# and project root is two levels up.
TEST_SCRIPT_PATH = Path(__file__).resolve() # tests/scripts/test_high_current.py
TESTS_DIR = TEST_SCRIPT_PATH.parent.parent # tests/
PROJECT_BASE_DIR = TESTS_DIR.parent # project root /app/

class TestHighCurrent(unittest.TestCase):

    def setUp(self):
        # Disable logging for most tests unless specifically testing log output
        # Use self.assertLogs for specific log checks, which temporarily enables logging.
        logging.disable(logging.CRITICAL)
        
        # Store original PROJECT_BASE_DIR from the module and patch it
        self.original_project_base_dir = high_current_module.PROJECT_BASE_DIR
        high_current_module.PROJECT_BASE_DIR = PROJECT_BASE_DIR

    def tearDown(self):
        # Restore logging state
        logging.disable(logging.NOTSET)
        # Restore original PROJECT_BASE_DIR
        high_current_module.PROJECT_BASE_DIR = self.original_project_base_dir


    def create_mock_indicator_df(self, symbol_name='TICK1', signal_date=datetime(2023,10,26).date()):
        """
        Creates a mock DataFrame as it would be returned by calculate_indicators,
        with enough data to pass checks in find_current_setups.
        The date of the latest record will be signal_date.
        """
        # Create a date range ending on signal_date
        dates = pd.to_datetime([signal_date - timedelta(days=x) for x in range(STRATEGY_PARAMS['min_data_days'] + 50)]).sort_values()

        data = {
            'Open': np.random.rand(len(dates)) * 100 + 50,
            'High': np.random.rand(len(dates)) * 10 + 150,
            'Low': np.random.rand(len(dates)) * 10 + 40,
            'Close': np.random.rand(len(dates)) * 100 + 50,
            'Volume': np.random.randint(100000, 500000, len(dates)),
            # Add other columns that calculate_indicators is expected to produce and detect_setup might use
            'ma5': np.random.rand(len(dates)) * 100,
            'ma20': np.random.rand(len(dates)) * 100,
            'ma50': np.random.rand(len(dates)) * 100,
            'ma200': np.random.rand(len(dates)) * 100,
            'rsi': np.random.rand(len(dates)) * 100,
            'ATR': np.random.rand(len(dates)) * 5,
            'day_thick_line_green': np.ones(len(dates)),
            'close_vs_open': np.random.rand(len(dates)) * 0.1,
            'volume_ratio': np.random.rand(len(dates)) * 2,
        }
        df = pd.DataFrame(data, index=dates)
        df.index.name = 'Date' # yfinance data usually has 'Date' index
        
        # Ensure the latest 'Close' is not NaN
        df.iloc[-1, df.columns.get_loc('Close')] = 100.0 
        # Ensure ATR is not NaN for the last record (used in trade_params)
        df.iloc[-1, df.columns.get_loc('ATR')] = 5.0

        return df

    # --- Tests for find_current_setups ---
    @patch('scripts.high_current.apply_high_probability_filter_live')
    @patch('scripts.high_current.calculate_potential_trade_params')
    @patch('scripts.high_current.detect_setup')
    @patch('scripts.high_current.calculate_indicators')
    @patch('scripts.high_current.fetch_stock_data_yf')
    @patch('scripts.high_current.load_symbols')
    def test_find_current_setups_signal_found(self, mock_load_symbols, mock_fetch_stock_data, 
                                             mock_calculate_indicators, mock_detect_setup,
                                             mock_calc_trade_params, mock_apply_filter):
        mock_load_symbols.return_value = ['TICK1']
        
        # Mock fetch_stock_data_yf to return a basic DataFrame (contents don't matter much here
        # as calculate_indicators is mocked)
        mock_df_raw = pd.DataFrame({'Close': [10,20]}, index=pd.to_datetime(['2023-01-01', '2023-01-02']))
        mock_fetch_stock_data.return_value = mock_df_raw
        
        signal_date_obj = datetime(2023, 10, 26).date() # Used for date assertion
        mock_df_indicators = self.create_mock_indicator_df('TICK1', signal_date=signal_date_obj)
        mock_calculate_indicators.return_value = mock_df_indicators
        
        # detect_setup returns: setup_detected, setup_type, tier
        mock_detect_setup.return_value = (True, 'MOCK_SETUP', 'high')

        mock_trade_params = {
            'entry_price': 100.0, 'stop_loss_price': 90.0, 'target_price': 120.0,
            'risk_reward_ratio': 2.0, 'atr': 5.0
        }
        mock_calc_trade_params.return_value = mock_trade_params
        mock_apply_filter.return_value = (True, 0.95) # passes_filter, score

        hist_perf_data = {
            'symbol': ['TICK1', 'TICK2'], # TICK2 ensures it picks TICK1
            'hist_strength_score': [np.nan, 70.0],
            'hist_win_rate': [-np.inf, 0.6],    
            'hist_total_trades': [pd.NA, 20] 
        }
        mock_hist_perf_df = pd.DataFrame(hist_perf_data)
        # Coerce 'hist_total_trades' to numeric, then to Int64 to handle NA, then fillna for np.nan if any non-convertible
        mock_hist_perf_df['hist_total_trades'] = pd.to_numeric(mock_hist_perf_df['hist_total_trades'], errors='coerce')


        with patch.object(high_current_module, 'long_term_historical_perf_df', mock_hist_perf_df):
            result = find_current_setups(STRATEGY_PARAMS)

        self.assertIsInstance(result, dict)
        self.assertTrue(result['signal_found'])
        self.assertEqual(result['symbol'], 'TICK1')
        self.assertIsInstance(result['date'], str) 
        self.assertEqual(result['date'], signal_date_obj.strftime('%Y-%m-%d'))
        self.assertEqual(result['setup_type'], 'MOCK_SETUP')
        self.assertEqual(result['tier'], 'high')
        self.assertEqual(result['strategy_score'], 0.95)
        
        self.assertIsNone(result['historical_strength_score'])
        self.assertIsNone(result['historical_win_rate'])
        self.assertIsNone(result['historical_total_trades'])

        self.assertEqual(result['latest_close'], mock_df_indicators['Close'].iloc[-1])
        self.assertEqual(result['entry_price'], 100.0)
        self.assertEqual(result['stop_loss_price'], 90.0)
        self.assertEqual(result['target_price'], 120.0)
        self.assertEqual(result['risk_reward_ratio'], 2.0)
        self.assertEqual(result['atr'], 5.0)

        self.assertIsInstance(result['strategy_score'], float)
        self.assertIsInstance(result['latest_close'], float)
        self.assertIsInstance(result['entry_price'], float)


    @patch('scripts.high_current.apply_high_probability_filter_live')
    @patch('scripts.high_current.calculate_potential_trade_params') 
    @patch('scripts.high_current.detect_setup') 
    @patch('scripts.high_current.calculate_indicators') 
    @patch('scripts.high_current.fetch_stock_data_yf')
    @patch('scripts.high_current.load_symbols')
    @patch('scripts.high_current.datetime') 
    def test_find_current_setups_no_signal_found(self, mock_datetime_hc, mock_load_symbols, mock_fetch_stock_data,
                                                mock_calculate_indicators, mock_detect_setup,
                                                mock_calc_trade_params, mock_apply_filter):
        mock_load_symbols.return_value = ['TICK1']
        mock_df_raw = pd.DataFrame({'Close': [10,20]}, index=pd.to_datetime(['2023-01-01', '2023-01-02']))
        mock_fetch_stock_data.return_value = mock_df_raw
        mock_df_indicators = self.create_mock_indicator_df('TICK1')
        mock_calculate_indicators.return_value = mock_df_indicators
        mock_detect_setup.return_value = (True, 'MOCK_SETUP', 'high') 
        mock_calc_trade_params.return_value = {'entry_price': 100.0, 'stop_loss_price': 90.0, 'target_price': 120.0, 'risk_reward_ratio': 2.0, 'atr': 5.0}
        mock_apply_filter.return_value = (False, 0.5) # Filtered out

        mock_datetime_hc.now.return_value = datetime(2023, 10, 27, 10, 0, 0)

        with patch.object(high_current_module, 'long_term_historical_perf_df', None):
            result = find_current_setups(STRATEGY_PARAMS)

        self.assertIsInstance(result, dict)
        self.assertFalse(result['signal_found'])
        self.assertEqual(result['date'], '2023-10-27')
        self.assertEqual(result['message'], 'No signal found today.')

    # --- Tests for generate_json_output ---

    @patch('scripts.high_current.logger') 
    @patch('builtins.print')
    @patch('os.environ')
    def test_generate_json_output_github_actions(self, mock_environ, mock_print, mock_logger_hc):
        mock_environ.get.return_value = 'true' 
        sample_data_signal = {'signal_found': True, 'symbol': 'TICK1', 'date': '2023-10-27'}
        
        generate_json_output(sample_data_signal)
        expected_json_signal = json.dumps(sample_data_signal, indent=4)
        mock_print.assert_called_with(expected_json_signal)
        mock_logger_hc.info.assert_any_call("Printing JSON to stdout for GitHub Action...")

        sample_data_no_signal = {'signal_found': False, 'date': '2023-10-27', 'message': 'No signal'}
        generate_json_output(sample_data_no_signal)
        expected_json_no_signal = json.dumps(sample_data_no_signal, indent=4)
        mock_print.assert_called_with(expected_json_no_signal) 
        
        self.assertEqual(mock_logger_hc.info.call_count, 2) 
        mock_logger_hc.info.assert_called_with("Printing JSON to stdout for GitHub Action...")


    @patch('scripts.high_current.logger')
    @patch('builtins.open', new_callable=mock_open)
    @patch('scripts.high_current.Path.mkdir')
    @patch('os.environ')
    @patch('scripts.high_current.datetime') 
    def test_generate_json_output_local_execution(self, mock_datetime_hc, mock_environ, mock_mkdir, mock_file_open, mock_logger_hc):
        mock_environ.get.return_value = 'false' 
        
        sample_data_signal = {'signal_found': True, 'symbol': 'TICK1', 'date': '2023-10-27'}
        expected_filename_signal = f"daily_signal_2023-10-27.json"
        expected_filepath_signal = PROJECT_BASE_DIR / "results" / "live_signals" / expected_filename_signal

        generate_json_output(sample_data_signal)
        
        mock_mkdir.assert_called_with(parents=True, exist_ok=True)
        mock_file_open.assert_called_with(expected_filepath_signal, 'w')
        mock_file_open().write.assert_called_with(json.dumps(sample_data_signal, indent=4))
        mock_logger_hc.info.assert_any_call(f"Saving JSON to file: {expected_filepath_signal}")

        mock_datetime_hc.now.return_value = datetime(2023, 10, 29) 
        sample_data_date_missing = {'signal_found': True, 'symbol': 'TICK2'} 
        expected_filename_date_missing = f"daily_signal_2023-10-29.json"
        expected_filepath_date_missing = PROJECT_BASE_DIR / "results" / "live_signals" / expected_filename_date_missing

        generate_json_output(sample_data_date_missing)
        mock_file_open.assert_called_with(expected_filepath_date_missing, 'w')
        mock_logger_hc.warning.assert_any_call("Signal date missing or not a string in signal_data; using current date for filename.")
        mock_logger_hc.info.assert_any_call(f"Saving JSON to file: {expected_filepath_date_missing}")


    @patch('scripts.high_current.logger')
    @patch('os.environ')
    def test_generate_json_output_json_error(self, mock_environ, mock_logger_hc):
        mock_environ.get.return_value = 'false' 
        non_serializable_data = {'data': object()} 

        generate_json_output(non_serializable_data)
        mock_logger_hc.error.assert_called_once()
        self.assertIn("Error serializing signal_data to JSON", mock_logger_hc.error.call_args[0][0])


    @patch('scripts.high_current.logger')
    @patch('builtins.open', new_callable=mock_open)
    @patch('scripts.high_current.Path.mkdir') # Mock mkdir as it's called before open
    @patch('os.environ')
    def test_generate_json_output_file_saving_error(self, mock_environ, mock_mkdir, mock_file_open, mock_logger_hc):
        mock_environ.get.return_value = 'false' 
        mock_file_open.side_effect = IOError("Failed to write")

        sample_data = {'signal_found': True, 'symbol': 'TICK1', 'date': '2023-10-27'}
        expected_filename = f"daily_signal_2023-10-27.json"
        # Use the same PROJECT_BASE_DIR as defined at the class/module level for tests
        expected_filepath = PROJECT_BASE_DIR / "results" / "live_signals" / expected_filename
        
        generate_json_output(sample_data)

        mock_mkdir.assert_called_with(parents=True, exist_ok=True)
        mock_file_open.assert_called_with(expected_filepath, 'w') 
        mock_logger_hc.error.assert_called_once()
        self.assertIn(f"IOError saving JSON to file {expected_filepath}", mock_logger_hc.error.call_args[0][0])


    # The existing test_find_current_setups_returns_sorted_list is commented out
    # as find_current_setups's primary return type has changed.
    # @patch('scripts.high_current.load_symbols')
    # @patch('scripts.high_current.fetch_stock_data_yf')
    # def test_find_current_setups_returns_sorted_list(self, mock_fetch_stock_data_yf, mock_load_symbols):
    #     """Test that find_current_setups returns a list of setups, sorted correctly."""
    #     # ... (original test code should be adapted or removed) ...
    #     pass


if __name__ == '__main__':
    # Ensure logging is not disabled when running file directly for debugging specific tests
    # logging.disable(logging.NOTSET) 
    # logging.basicConfig(level=logging.DEBUG) # Or INFO
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
