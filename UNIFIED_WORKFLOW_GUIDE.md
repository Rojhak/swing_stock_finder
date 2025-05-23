# Unified Workflow Guide

This document explains how the unified GitHub Actions workflow (`unified_daily_report.yml`) operates in the stock trading signal system.

## Overview

The unified workflow replaces multiple separate workflows to provide a streamlined, robust process that:

1. Generates trading signals
2. Creates enhanced reports
3. Automatically tracks signals as trades
4. Sends email notifications through multiple methods for reliability

## Workflow Execution

The workflow runs:
- Daily at 8:00 AM UTC
- Manually triggered through GitHub Actions interface using `workflow_dispatch`

## Process Steps

### 1. Signal Generation
- Runs `high_current.py` to scan markets and identify potential trades
- Outputs JSON files with trade details to `results/live_signals/`
- Captures console output to `signal_output.txt`

### 2. Enhanced Reporting
- Locates the latest signal JSON file
- Processes it using `enhanced_report.py`
- Creates a human-readable report
- Adds additional analytics and tracking information

### 3. Trade Tracking
- Uses `auto_tracker.py` to automatically track signals in the trade management system
- Only tracks the overall signal by default (not segment-specific signals)
- Updates the `trades.csv` file with the new tracked signal
- Updates prices and performance metrics of active trades

### 4. Notification
- Primary method: Uses `enhanced_report.py`'s built-in email functionality
- Fallback method: Uses GitHub Action's email sending mechanism
- Both methods use the same SMTP credentials for consistency

### 5. Artifact Storage
- Archives report files for 7 days for debugging purposes
- Stores generated signal JSONs, reports, and log outputs

## Configuration Requirements

For proper operation, the workflow requires:
1. Repository secrets:
   - `MAIL_USERNAME`: SMTP username for email notifications
   - `MAIL_PASSWORD`: SMTP password for email notifications

2. Environment setup:
   - Python 3.9
   - Dependencies: pandas, numpy, yfinance, tqdm

## Customizing the Workflow

To change the behavior of the workflow:

1. **Signal tracking behavior**: Edit the `auto_tracker.py` parameters in the workflow
   - Add `--track-all` to track both overall and segment-specific signals
   - Add `--dry-run` to simulate tracking without making changes

2. **Email recipients**: Update the `to:` field in both email sending steps

3. **Schedule**: Modify the `cron` expression in the workflow trigger

## Manual Execution

You can manually trigger the workflow in GitHub:
1. Go to the Actions tab in your repository
2. Select "Unified Daily Report Workflow"
3. Click "Run workflow"

## Troubleshooting

If issues occur:
1. Check the workflow run logs in GitHub Actions
2. Download the archived artifacts for detailed logs
3. Verify SMTP credentials are correct
4. Ensure all required Python dependencies are installed

## Reverting to Previous Workflows

If needed, restore the previous workflows from `.github/workflows_backup/`.
