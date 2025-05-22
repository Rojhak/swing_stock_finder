import unittest
import pandas as pd
import os
import logging
from unittest.mock import patch, MagicMock, call

# Adjust import path to go up one level from 'tests/scripts' to the project root, then into 'scripts'
import sys
# SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # This is tests/scripts
# PROJECT_BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR)) # This is the project root
# sys.path.append(PROJECT_BASE_DIR) # Add project root to sys.path

# Assuming the tests are run from the project root directory (e.g., using python -m unittest discover tests)
# or that the PYTHONPATH is set up correctly.
from scripts.historical_analyzer import get_top_historical_picks, HISTORICAL_PERF_FILE_PATH

# Disable logging for tests unless specifically testing for log messages
logging.disable(logging.CRITICAL)

class TestHistoricalAnalyzer(unittest.TestCase):

    def setUp(self):
        """Set up sample data for tests."""
        self.sample_data = {
            'symbol': ['SYM1', 'SYM2', 'SYM3', 'SYM4', 'SYM5', 'SYM6'],
            'hist_win_rate': [0.8, 0.9, 0.7, 0.85, 0.95, 0.75],
            'hist_avg_pnl': [5.0, 6.5, 4.0, 5.5, 7.0, 4.5],
            'hist_strength_score': [100, 120, 90, 110, 130, 95],
            'other_metric': [1, 2, 3, 4, 5, 6]
        }
        self.sample_df = pd.DataFrame(self.sample_data)

        self.expected_keys = ['symbol', 'hist_win_rate', 'hist_avg_pnl', 'hist_strength_score']

    @patch('scripts.historical_analyzer.os.path.exists')
    @patch('scripts.historical_analyzer.pd.read_csv')
    def test_get_top_picks_normal_case(self, mock_read_csv, mock_exists):
        """Test normal case with more than 5 rows."""
        mock_exists.return_value = True
        mock_read_csv.return_value = self.sample_df.copy()

        result = get_top_historical_picks()
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0]['symbol'], 'SYM5') # SYM5 has score 130
        self.assertEqual(result[1]['symbol'], 'SYM2') # SYM2 has score 120
        self.assertEqual(result[4]['symbol'], 'SYM6') # SYM6 has score 95

        for item in result:
            self.assertEqual(sorted(list(item.keys())), sorted(self.expected_keys))
            self.assertIsNotNone(item['hist_strength_score'])


    @patch('scripts.historical_analyzer.os.path.exists')
    @patch('scripts.historical_analyzer.pd.read_csv')
    def test_get_top_picks_less_than_5_rows(self, mock_read_csv, mock_exists):
        """Test case with less than 5 rows in CSV."""
        mock_exists.return_value = True
        less_data_df = self.sample_df.head(3).copy()
        mock_read_csv.return_value = less_data_df

        result = get_top_historical_picks()
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]['symbol'], 'SYM2') # SYM2 score 120
        self.assertEqual(result[1]['symbol'], 'SYM1') # SYM1 score 100
        self.assertEqual(result[2]['symbol'], 'SYM3') # SYM3 score 90
        for item in result:
            self.assertEqual(sorted(list(item.keys())), sorted(self.expected_keys))

    @patch('scripts.historical_analyzer.os.path.exists')
    @patch('scripts.historical_analyzer.pd.read_csv')
    def test_get_top_picks_empty_file(self, mock_read_csv, mock_exists):
        """Test case with an empty CSV file."""
        mock_exists.return_value = True
        mock_read_csv.return_value = pd.DataFrame(columns=self.sample_data.keys())

        result = get_top_historical_picks()
        self.assertEqual(len(result), 0)

    @patch('scripts.historical_analyzer.logger.error')
    @patch('scripts.historical_analyzer.os.path.exists')
    def test_get_top_picks_file_not_found(self, mock_exists, mock_logger_error):
        """Test case where the CSV file does not exist."""
        mock_exists.return_value = False
        
        # HISTORICAL_PERF_FILE_PATH is used directly in the module, so patching os.path.exists 
        # that is used by the module is the way to go.
        
        result = get_top_historical_picks()
        self.assertEqual(len(result), 0)
        mock_logger_error.assert_called_once_with(f"Historical performance file not found: {HISTORICAL_PERF_FILE_PATH}")

    @patch('scripts.historical_analyzer.logger.error')
    @patch('scripts.historical_analyzer.os.path.exists')
    @patch('scripts.historical_analyzer.pd.read_csv')
    def test_get_top_picks_missing_column(self, mock_read_csv, mock_exists, mock_logger_error):
        """Test case where 'hist_strength_score' column is missing."""
        mock_exists.return_value = True
        df_missing_col = self.sample_df.drop(columns=['hist_strength_score'])
        mock_read_csv.return_value = df_missing_col

        result = get_top_historical_picks()
        self.assertEqual(len(result), 0)
        mock_logger_error.assert_called_once_with("Required column 'hist_strength_score' not found in the historical performance data.")

    @patch('scripts.historical_analyzer.os.path.exists')
    @patch('scripts.historical_analyzer.pd.read_csv')
    def test_get_top_picks_non_numeric_score(self, mock_read_csv, mock_exists):
        """Test handling of non-numeric hist_strength_score values."""
        mock_exists.return_value = True
        data_with_non_numeric = self.sample_df.copy()
        # Introduce non-numeric and NaN values
        data_with_non_numeric.loc[0, 'hist_strength_score'] = 'not_a_number'
        data_with_non_numeric.loc[1, 'hist_strength_score'] = None # This will become NaN
        data_with_non_numeric.loc[2, 'hist_strength_score'] = 90 # Valid
        data_with_non_numeric.loc[3, 'hist_strength_score'] = 110 # Valid
        data_with_non_numeric.loc[4, 'hist_strength_score'] = 'another_string'
        data_with_non_numeric.loc[5, 'hist_strength_score'] = 95 # Valid
        
        mock_read_csv.return_value = data_with_non_numeric
        
        result = get_top_historical_picks()
        
        # Expected: SYM3 (90), SYM6 (95), SYM4 (110) after sorting valid numeric scores
        # The function should convert bad scores to NaN and drop them.
        self.assertEqual(len(result), 3) 
        self.assertTrue(all(isinstance(item['hist_strength_score'], (int, float)) for item in result))
        self.assertEqual(result[0]['symbol'], 'SYM4') # 110
        self.assertEqual(result[1]['symbol'], 'SYM6') # 95
        self.assertEqual(result[2]['symbol'], 'SYM3') # 90


    @patch('scripts.historical_analyzer.os.path.exists')
    @patch('scripts.historical_analyzer.pd.read_csv')
    def test_get_top_picks_all_scores_nan_after_coercion(self, mock_read_csv, mock_exists):
        """Test when all scores become NaN after numeric coercion."""
        mock_exists.return_value = True
        df_all_bad_scores = pd.DataFrame({
            'symbol': ['SYM1', 'SYM2'],
            'hist_win_rate': [0.8, 0.9],
            'hist_avg_pnl': [5.0, 6.5],
            'hist_strength_score': ['bad', 'score'], # All non-numeric
            'other_metric': [1, 2]
        })
        mock_read_csv.return_value = df_all_bad_scores
        
        with patch('scripts.historical_analyzer.logger.warning') as mock_logger_warning:
            result = get_top_historical_picks()
            self.assertEqual(len(result), 0)
            # Check if the specific warning for empty df after dropna was logged
            # This depends on the exact logging message in historical_analyzer.py
            # For example: "Historical performance DataFrame is empty after handling non-numeric scores."
            # Let's assume such a message exists, or we can just check if warning was called.
            mock_logger_warning.assert_any_call("Historical performance DataFrame is empty after handling non-numeric scores.")


if __name__ == '__main__':
    # This allows running the tests directly from this file
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
