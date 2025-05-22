import unittest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, call
from datetime import datetime, date

# Assuming tests are run from the project root directory
from scripts.high_current import find_current_setups, STRATEGY_PARAMS, load_symbols, fetch_stock_data_yf
import scripts.high_current as high_current_module # To patch globals like long_term_historical_perf_df

# Disable logging for tests
import logging
logging.disable(logging.CRITICAL)

class TestHighCurrent(unittest.TestCase):

    def create_mock_stock_data(self, symbol, setup_type='BOTTOM_TURN'):
        """Helper to create DataFrame that can trigger a setup."""
        base_date = datetime(2023, 1, 1)
        dates = pd.to_datetime([base_date - pd.Timedelta(days=x) for x in range(260)]).sort_values()
        
        data = {
            'Open': np.random.rand(260) * 100 + 50,
            'High': np.random.rand(260) * 10 + 150,
            'Low': np.random.rand(260) * 10 + 40,
            'Close': np.random.rand(260) * 100 + 50,
            'Volume': np.random.randint(100000, 500000, 260)
        }
        df = pd.DataFrame(data, index=dates)
        
        # Add basic MAs and RSI to trigger setups, values are somewhat arbitrary but aim to meet conditions
        df['ma5'] = df['Close'].rolling(window=5).mean()
        df['ma20'] = df['Close'].rolling(window=20).mean()
        df['ma50'] = df['Close'].rolling(window=50).mean()
        df['ma200'] = df['Close'].rolling(window=200).mean()
        
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'].fillna(50, inplace=True)

        df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean() # Simplified ATR
        df['ATR'].fillna(1, inplace=True) # Ensure ATR is not NaN

        # For setup_type = 'BOTTOM_TURN' (rsi related)
        if setup_type == 'BOTTOM_TURN':
            df.iloc[-2, df.columns.get_loc('rsi')] = 25 # Previous RSI < 30
            df.iloc[-1, df.columns.get_loc('rsi')] = 35 # Current RSI > 30
            df.iloc[-1, df.columns.get_loc('day_thick_line_green')] = 1 # Condition for BOTTOM_TURN
        
        # For setup_type = 'VOLUME_SPIKE'
        elif setup_type == 'VOLUME_SPIKE':
            df['volume_ratio'] = 1.0 # Default
            df.iloc[-1, df.columns.get_loc('volume_ratio')] = STRATEGY_PARAMS['volume_spike_threshold'] + 0.5
            df.iloc[-1, df.columns.get_loc('close_vs_open')] = 0.01 # Positive close_vs_open

        # Fill NaNs resulting from rolling means, etc.
        df.bfill(inplace=True) # Backfill first to handle initial NaNs
        df.ffill(inplace=True) # Then ffill to handle any remaining (though bfill should get most)
        
        # Ensure critical columns for detect_setup are present after indicator calculation
        # These are added by calculate_indicators, here we ensure they have some default values if not set above.
        df['day_thick_line_green'] = df.get('day_thick_line_green', 1)
        df['close_vs_open'] = df.get('close_vs_open', 0.01)
        df['volume_ratio'] = df.get('volume_ratio', 1.0)


        # Ensure enough data points after all calculations
        if len(df) < STRATEGY_PARAMS['min_data_days']:
             # If after filling, still not enough, this mock data is too small
             # This shouldn't happen with 260 days initial data.
             return None 
        return df

    @patch('scripts.high_current.load_symbols')
    @patch('scripts.high_current.fetch_stock_data_yf')
    def test_find_current_setups_returns_sorted_list(self, mock_fetch_stock_data_yf, mock_load_symbols):
        """Test that find_current_setups returns a list of setups, sorted correctly."""
        mock_load_symbols.return_value = ['TICK1', 'TICK2', 'TICK3', 'TICK4_FAIL']

        # Mock historical performance data
        hist_perf_data = {
            'symbol': ['TICK1', 'TICK2', 'TICK3'],
            'hist_strength_score': [80.0, 95.0, 90.0], # TICK2 stronger hist_strength
            'hist_win_rate': [0.7, 0.8, 0.75],
            'hist_total_trades': [10, 15, 12]
        }
        mock_hist_perf_df = pd.DataFrame(hist_perf_data)
        
        # Prepare mock return values for fetch_stock_data_yf
        # TICK1: generates setup, lower primary score
        df_tick1 = self.create_mock_stock_data('TICK1', setup_type='BOTTOM_TURN')
        # Manually tweak values that influence the 'score' to ensure sorting can be tested
        # Let's assume default risk_reward_ratio is high enough.
        # For TICK1, let score components be moderate.
        # (The actual score calculation is complex, so direct manipulation of df for precise score is hard.
        # Instead, we rely on detect_setup and apply_high_probability_filter_live finding these).

        # TICK2: generates setup, higher primary score
        df_tick2 = self.create_mock_stock_data('TICK2', setup_type='VOLUME_SPIKE') 
        # For TICK2, make it a volume spike which gets higher base score in filter.

        # TICK3: generates setup, same primary score as TICK2, but lower historical strength
        df_tick3 = self.create_mock_stock_data('TICK3', setup_type='VOLUME_SPIKE')

        # TICK4_FAIL: does not generate a setup (e.g., returns None or empty df)
        
        def side_effect_fetch_data(symbol, period):
            if symbol == 'TICK1': return df_tick1
            if symbol == 'TICK2': return df_tick2
            if symbol == 'TICK3': return df_tick3
            if symbol == 'TICK4_FAIL': return None # Or pd.DataFrame()
            return None
        mock_fetch_stock_data_yf.side_effect = side_effect_fetch_data

        # Patch the global long_term_historical_perf_df in the high_current module
        with patch.object(high_current_module, 'long_term_historical_perf_df', mock_hist_perf_df):
            results = find_current_setups(STRATEGY_PARAMS)

        self.assertIsInstance(results, list)
        self.assertTrue(len(results) <= 3) # Max 3 should pass if all generate setups

        if len(results) > 1:
            # Check sorting: Primary by 'score' (desc), secondary by 'hist_strength_score' (desc)
            # This requires knowing the scores. apply_high_probability_filter_live gives:
            # BOTTOM_TURN: 25 base. VOLUME_SPIKE: 35 base (if prioritize_volume_spike=True)
            # R:R part adds to score. For simplicity, assume R:R is same for all.
            # TICK1 (BOTTOM_TURN) score will be lower than TICK2/TICK3 (VOLUME_SPIKE)
            # TICK2 hist_strength_score (95) > TICK3 hist_strength_score (90)

            # Expected order: TICK2, TICK3, TICK1 (if all pass filter with these scores)
            # Scores: TICK2 & TICK3 (VOLUME_SPIKE) will be higher than TICK1 (BOTTOM_TURN)
            # Tie-break TICK2 vs TICK3: TICK2 (hist 95) > TICK3 (hist 90)

            # Verify this by checking 'symbol' order after scores are calculated
            # Note: The exact scores depend on R:R ratio which comes from ATR, making it complex to mock perfectly.
            # We are checking if the sorting logic is generally followed.
            
            # Log actual scores for debugging if test fails
            # for r in results:
            #    print(f"Symbol: {r['symbol']}, Score: {r['score']}, HistStrength: {r['hist_strength_score']}")

            scores = [(r['symbol'], r['score'], r['hist_strength_score']) for r in results]
            
            # Check that results are sorted by score (desc) then hist_strength_score (desc)
            # This is a bit indirect. We check if any pair is out of order.
            for i in range(len(scores) - 1):
                current_score, current_hist = scores[i][1], scores[i][2]
                next_score, next_hist = scores[i+1][1], scores[i+1][2]
                
                self.assertTrue(current_score > next_score or \
                                (current_score == next_score and current_hist >= next_hist))

        # Check structure of each dict
        expected_keys = [
            'symbol', 'date', 'setup_type', 'tier', 'score', 'entry_price', 
            'stop_loss_price', 'target_price', 'risk_reward_ratio', 'atr',
            'latest_close', 'hist_strength_score', 'hist_win_rate', 'hist_total_trades'
        ]
        for item in results:
            self.assertEqual(len(item.keys()), len(expected_keys))
            for key in expected_keys:
                self.assertIn(key, item)
            self.assertIsInstance(item['date'], date)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
