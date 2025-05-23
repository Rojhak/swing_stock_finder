# Automated Signal Tracker

This script automatically connects the signal generation system (high_current.py) with the trade tracking system (tracking_manager.py).

## Purpose

The Automated Signal Tracker bridges the gap between signal generation and trade tracking by:

1. Finding and loading the latest signal JSON file
2. Converting signals to the format expected by the tracking system
3. Adding signals to the tracking system as active trades
4. Updating current prices for all active trades

## Usage

### Basic Usage

```bash
# Track the latest overall signal
python auto_tracker.py

# Track all signals (overall and per-segment)
python auto_tracker.py --track-all

# Track signals from a specific file
python auto_tracker.py --file results/live_signals/daily_signal_2025-05-20.json

# Preview what would be tracked without actually tracking
python auto_tracker.py --dry-run
```

### Integration with Workflow

The `auto_tracker.py` script is designed to be used in the following workflow:

1. `high_current.py` generates signals and outputs to JSON
2. `auto_tracker.py` adds signals to tracking
3. Users manually close trades or implement auto-close logic

## Signal Selection

By default, only the overall top signal is tracked. Use the `--track-all` flag to track segment-specific signals as well.

## Implementation Details

The script:
1. Uses the `tracking_manager.py` module's functions
2. Converts signals to the required format
3. Skips duplicate signals (same symbol tracked multiple times)
4. Updates prices after tracking for immediate P&L calculation

## Best Practices

- Use `--dry-run` to preview tracking before committing
- Use `--track-all` only when you want to track multiple signals from different market segments
- Run `update_active_trades()` from tracking_manager.py to update prices and P&L
