import unittest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, call, mock_open
from datetime import datetime, date, timedelta
import json
from pathlib import Path
import logging

from scripts.high_current import (
    find_current_setups, 
    generate_json_output, 
    main as high_current_main,
    _print_signal_details_to_console,
    STRATEGY_PARAMS,
    TICKER_FILES 
)
import scripts.high_current as high_current_module

TEST_SCRIPT_PATH = Path(__file__).resolve()
TESTS_DIR = TEST_SCRIPT_PATH.parent.parent
PROJECT_BASE_DIR = TESTS_DIR.parent

class TestHighCurrent(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.original_project_base_dir = high_current_module.PROJECT_BASE_DIR
        high_current_module.PROJECT_BASE_DIR = PROJECT_BASE_DIR
        
        self.mock_datetime_patch = patch('scripts.high_current.datetime')
        self.mock_datetime = self.mock_datetime_patch.start()
        self.mock_datetime.now.return_value = datetime(2023, 10, 27, 10, 0, 0) # Consistent "now" for tests

    def tearDown(self):
        logging.disable(logging.NOTSET)
        high_current_module.PROJECT_BASE_DIR = self.original_project_base_dir
        self.mock_datetime_patch.stop()

    def _create_mock_df_for_symbol(self, symbol, signal_date_val):
        """ Helper to create a DataFrame that can be returned by calculate_indicators. """
        # Using a passed-in signal_date_val which should be a datetime.date object
        dates = pd.to_datetime([signal_date_val - timedelta(days=x) for x in range(STRATEGY_PARAMS['min_data_days'] + 50)]).sort_values()
        
        # Basic structure, can be customized further per test if needed
        data = {
            'Open': np.full(len(dates), 100.0), 'High': np.full(len(dates), 105.0),
            'Low': np.full(len(dates), 95.0), 'Close': np.full(len(dates), 100.0),
            'Volume': np.full(len(dates), 100000),
            'ma5': np.full(len(dates), 100.0), 'ma20': np.full(len(dates), 100.0),
            'ma50': np.full(len(dates), 100.0), 'ma200': np.full(len(dates), 100.0),
            'rsi': np.full(len(dates), 50.0), 'ATR': np.full(len(dates), 5.0),
            'day_thick_line_green': np.ones(len(dates)),
            'close_vs_open': np.full(len(dates), 0.01),
            'volume_ratio': np.full(len(dates), 1.5),
        }
        df = pd.DataFrame(data, index=dates)
        df.name = symbol # Set df.name to allow identification in later mocks
        df.iloc[-1, df.columns.get_loc('Close')] = 100.0  # Ensure last close is valid
        df.iloc[-1, df.columns.get_loc('ATR')] = 5.0      # Ensure last ATR is valid
        return df

    @patch('scripts.high_current.apply_high_probability_filter_live')
    @patch('scripts.high_current.calculate_potential_trade_params')
    @patch('scripts.high_current.detect_setup')
    @patch('scripts.high_current.calculate_indicators')
    @patch('scripts.high_current.fetch_stock_data_yf')
    @patch('scripts.high_current.load_symbols')
    def test_find_current_setups_complex_scenarios(self, mock_load_symbols, mock_fetch_stock_data,
                                                 mock_calculate_indicators, mock_detect_setup,
                                                 mock_calc_trade_params, mock_apply_filter):
        
        signal_date_obj = datetime(2023, 10, 26).date()
        
        # Common mock behaviors
        mock_detect_setup.return_value = (True, 'MOCK_SETUP', 'high')
        mock_calc_trade_params.side_effect = lambda df, entry_idx: {
            'entry_price': 100.0, 'stop_loss_price': 90.0, 'target_price': 120.0,
            'risk_reward_ratio': 2.0, 'atr': 5.0 # df.name (symbol) will be used by apply_filter
        }
        mock_calculate_indicators.side_effect = lambda df: df # Pass through df from fetch
        mock_fetch_stock_data.side_effect = lambda symbol, period: self._create_mock_df_for_symbol(symbol, signal_date_obj)

        # --- Scenario 1: Overall signal found, signals in all segments ---
        mock_load_symbols.return_value = {'market1': ['M1S1', 'M1S2'], 'market2': ['M2S1']}
        
        def apply_filter_s1(trade_params, setup_type, tier, params_dict):
            # Assuming trade_params now gets symbol via df.name passed through to setup_info
            # The 'score' is in setup_info which is then passed to _format_signal_output
            # For simplicity, we'll assume the symbol is available in the dict passed to apply_filter
            # This requires setup_info to be constructed before apply_filter_live, which is not the case.
            # Instead, the symbol is known when fetch_stock_data is called.
            # The mock chain needs to ensure the score is associated with the symbol correctly.
            # Let's mock `apply_high_probability_filter_live` based on the symbol implicitly known from `fetch_stock_data_yf`'s current symbol.
            # This is tricky because `apply_high_probability_filter_live` doesn't directly receive the symbol.
            # We need to make `mock_apply_filter` aware of the current symbol being processed.
            # One way: Use a global or class variable in the test, set by `mock_fetch_stock_data`. This is hacky.
            # Better way: `mock_apply_filter` is part of the loop, so if we can make its behavior conditional.
            # The current symbol IS available in `find_current_setups` loop.
            # For the test, let's make `mock_apply_filter`'s behavior depend on something passed to it,
            # or make it stateful based on call order if symbols are processed predictably.
            # Simplest: make `apply_filter_live` return values based on pre-set scores for symbols.
            current_symbol = mock_fetch_stock_data.call_args[0][0] # Get symbol from last call to fetch_stock_data
            if current_symbol == 'M1S1': return (True, 0.95) # Overall top
            if current_symbol == 'M1S2': return (True, 0.85)
            if current_symbol == 'M2S1': return (True, 0.90)
            return (False, 0.0)
        mock_apply_filter.side_effect = apply_filter_s1

        hist_data_s1 = {'symbol': ['M1S1', 'M1S2', 'M2S1'], 'hist_strength_score': [90,80,85], 'hist_win_rate': [0.7,0.6,0.65], 'hist_total_trades': [10,12,15]}
        with patch.object(high_current_module, 'long_term_historical_perf_df', pd.DataFrame(hist_data_s1)):
            result_s1 = find_current_setups(STRATEGY_PARAMS)

        self.assertTrue(result_s1['overall_top_signal']['signal_found'])
        self.assertEqual(result_s1['overall_top_signal']['symbol'], 'M1S1')
        self.assertEqual(result_s1['overall_top_signal']['market_segment'], 'market1')
        self.assertEqual(result_s1['overall_top_signal']['date'], '2023-10-26')
        self.assertTrue(result_s1['segmented_signals']['market1']['signal_found'])
        self.assertEqual(result_s1['segmented_signals']['market1']['symbol'], 'M1S1') # M1S1 score 0.95 > M1S2 score 0.85
        self.assertTrue(result_s1['segmented_signals']['market2']['signal_found'])
        self.assertEqual(result_s1['segmented_signals']['market2']['symbol'], 'M2S1')

        # --- Scenario 2: Overall signal found, market2 no signal ---
        def apply_filter_s2(trade_params, setup_type, tier, params_dict):
            current_symbol = mock_fetch_stock_data.call_args[0][0]
            if current_symbol == 'M1S1': return (True, 0.95)
            if current_symbol == 'M1S2': return (True, 0.85)
            if current_symbol == 'M2S1': return (False, 0.40) # M2S1 fails filter
            return (False, 0.0)
        mock_apply_filter.side_effect = apply_filter_s2
        with patch.object(high_current_module, 'long_term_historical_perf_df', pd.DataFrame(hist_data_s1)):
            result_s2 = find_current_setups(STRATEGY_PARAMS)
        
        self.assertTrue(result_s2['overall_top_signal']['signal_found'])
        self.assertEqual(result_s2['overall_top_signal']['symbol'], 'M1S1')
        self.assertTrue(result_s2['segmented_signals']['market1']['signal_found'])
        self.assertEqual(result_s2['segmented_signals']['market1']['symbol'], 'M1S1')
        self.assertFalse(result_s2['segmented_signals']['market2']['signal_found'])
        self.assertEqual(result_s2['segmented_signals']['market2']['date'], '2023-10-27') # Default "now" date

        # --- Scenario 3: No overall signal (all fail filter) ---
        mock_apply_filter.return_value = (False, 0.4) # All symbols fail
        with patch.object(high_current_module, 'long_term_historical_perf_df', pd.DataFrame(hist_data_s1)):
            result_s3 = find_current_setups(STRATEGY_PARAMS)

        self.assertFalse(result_s3['overall_top_signal']['signal_found'])
        self.assertEqual(result_s3['overall_top_signal']['date'], '2023-10-27') # Default "now"
        self.assertFalse(result_s3['segmented_signals']['market1']['signal_found'])
        self.assertFalse(result_s3['segmented_signals']['market2']['signal_found'])
        # Ensure all configured markets are present in segmented_signals
        for market_key in TICKER_FILES.keys():
            self.assertIn(market_key, result_s3['segmented_signals'])
            self.assertFalse(result_s3['segmented_signals'][market_key]['signal_found'])


    @patch('builtins.print')
    def test_print_signal_details_console(self, mock_print):
        title = "Test Title"
        # Test signal found
        signal_data_found = {
            'signal_found': True, 'symbol': 'XYZ', 'date': '2023-01-15', 'market_segment': 'test_market',
            'setup_type': 'TestSetup', 'tier': 'High', 'strategy_score': 0.987,
            'historical_strength_score': 75.5, 'historical_win_rate': 0.65, 'historical_total_trades': 30,
            'latest_close': 123.45, 'entry_price': 124.00, 'stop_loss_price': 120.00,
            'target_price': 130.00, 'risk_reward_ratio': 1.5, 'atr': 2.500
        }
        _print_signal_details_to_console(signal_data_found, title)
        
        # Basic checks for content
        calls = [c[0][0] for c in mock_print.call_args_list] # Get the first arg of each print call
        self.assertIn(f"\n{title}", calls)
        self.assertTrue(any("Symbol: XYZ" in c for c in calls))
        self.assertTrue(any("Strategy Score: 0.987" in c for c in calls))
        self.assertTrue(any("Win Rate: 65.00%" in c for c in calls))
        mock_print.reset_mock()

        # Test signal not found
        signal_data_not_found = {'signal_found': False, 'message': 'No signal here.'}
        _print_signal_details_to_console(signal_data_not_found, title)
        calls = [c[0][0] for c in mock_print.call_args_list]
        self.assertIn(f"\n{title}", calls)
        self.assertTrue(any("No signal here." in c for c in calls))
        mock_print.reset_mock()

        # Test empty dict
        _print_signal_details_to_console({}, title)
        calls = [c[0][0] for c in mock_print.call_args_list]
        self.assertIn(f"\n{title}", calls)
        self.assertTrue(any("No signal data provided" in c for c in calls))


    @patch('scripts.high_current.logger')
    @patch('builtins.print')
    @patch('os.environ')
    def test_generate_json_output_github_actions_complex(self, mock_environ, mock_print, mock_logger_hc):
        mock_environ.get.return_value = 'true'
        complex_data = {
            'overall_top_signal': {'signal_found': True, 'symbol': 'OVERALL', 'date': '2023-10-26'},
            'segmented_signals': {'market1': {'signal_found': False, 'message': 'No M1 signal'}}
        }
        generate_json_output(complex_data)
        expected_json = json.dumps(complex_data, indent=4)
        mock_print.assert_called_with(expected_json)
        mock_logger_hc.info.assert_any_call("Printing complex signal data (overall and segmented) to stdout for GitHub Action...")


    @patch('scripts.high_current.logger')
    @patch('builtins.open', new_callable=mock_open)
    @patch('scripts.high_current.Path.mkdir')
    @patch('os.environ')
    # mock_datetime is already active from setUp
    def test_generate_json_output_local_execution_date_logic(self, mock_environ, mock_mkdir, mock_file_open, mock_logger_hc):
        mock_environ.get.return_value = 'false'
        
        # Case 1: Date from overall_top_signal
        data_overall_date = {'overall_top_signal': {'signal_found': True, 'date': '2023-01-01'}, 'segmented_signals': {}}
        generate_json_output(data_overall_date)
        expected_path1 = PROJECT_BASE_DIR / "results" / "live_signals" / "daily_signal_2023-01-01.json"
        mock_file_open.assert_called_with(expected_path1, 'w')

        # Case 2: Date from segmented_signals
        data_segment_date = {
            'overall_top_signal': {'signal_found': False, 'message': 'No overall'},
            'segmented_signals': {'market1': {'signal_found': True, 'date': '2023-02-01'}}
        }
        generate_json_output(data_segment_date)
        expected_path2 = PROJECT_BASE_DIR / "results" / "live_signals" / "daily_signal_2023-02-01.json"
        mock_file_open.assert_called_with(expected_path2, 'w')

        # Case 3: Fallback to current date (mocked by self.mock_datetime.now)
        data_fallback_date = {'overall_top_signal': {'signal_found': False}, 'segmented_signals': {'market1': {'signal_found': False}}}
        generate_json_output(data_fallback_date)
        expected_path3 = PROJECT_BASE_DIR / "results" / "live_signals" / "daily_signal_2023-10-27.json" # From setUp
        mock_file_open.assert_called_with(expected_path3, 'w')
        mock_logger_hc.warning.assert_any_call("Could not determine signal date from overall or segmented signals; using current date for filename.")

    @patch('scripts.high_current._print_signal_details_to_console')
    @patch('scripts.high_current.generate_json_output')
    @patch('scripts.high_current.find_current_setups')
    @patch('scripts.high_current.load_long_term_historical_stats')
    def test_main_function_orchestration_and_console_output(self, mock_load_hist, mock_find_setups, 
                                                             mock_gen_json, mock_print_details):
        mock_overall_signal = {'signal_found': True, 'symbol': 'OVERALL', 'market_segment': 'market1', 'date': '2023-10-27'}
        mock_segment1_signal = {'signal_found': True, 'symbol': 'M1S1', 'market_segment': 'market1', 'date': '2023-10-27'}
        mock_segment2_no_signal = {'signal_found': False, 'message': 'No M2', 'market_segment': 'market2', 'date': '2023-10-27'}
        
        complex_data_mock = {
            'overall_top_signal': mock_overall_signal,
            'segmented_signals': { 'market1': mock_segment1_signal, 'market2': mock_segment2_no_signal }
        }
        mock_find_setups.return_value = complex_data_mock

        high_current_main()

        mock_load_hist.assert_called_once()
        mock_find_setups.assert_called_once_with(STRATEGY_PARAMS)
        mock_gen_json.assert_called_once_with(complex_data_mock)
        
        expected_calls = [
            call(mock_overall_signal, "--- Overall Top Selected Trade Candidate for Today ---"),
            call(mock_segment1_signal, "--- Top Signal for MARKET1 Market ---"),
            call(mock_segment2_no_signal, "--- Top Signal for MARKET2 Market ---")
        ]
        mock_print_details.assert_has_calls(expected_calls, any_order=False)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
```
