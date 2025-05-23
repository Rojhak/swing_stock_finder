"""
Tracking Manager for Trading Signals

This module manages the lifecycle of trades based on signals from high_current.py:

SIGNAL GENERATION & TRADE TRACKING WORKFLOW:
-------------------------------------------
1. Signal Generation (high_current.py):
   - Generates trading signals by scanning stock markets
   - Outputs JSON files to results/live_signals/

2. Report Generation (enhanced_report.py):
   - Formats JSON data into human-readable reports
   - Tracks changes in signals over time
   - Sends email reports

3. Trade Management (tracking_manager.py - this module):
   - MANUAL STEP: Add signals to tracking using add_tracked_signal()
   - Update current prices with update_active_trades()
   - MANUAL STEP: Close trades using close_trade() when targets hit or stops triggered

Integration Options:
- Manual: Use tracking_manager.py functions directly from Python code or CLI
- Automated: Use auto_tracker.py to automatically track latest signals

For automated trading integration, consider the following workflow:
1. high_current.py generates signals
2. auto_tracker.py tracks signals as trades
3. User manually closes trades or implements auto-close logic
"""
