#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced Report Generator

This script consolidates all the needed functionality for:
1. Properly formatting the report from JSON data
2. Tracking signal changes over time (without pandas dependency)
3. Sending emails reliably (with extensive error handling)
"""

import os
import json
import glob
from pathlib import Path
import datetime
import logging
import sys
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import platform
import socket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_email_credentials():
    logger.info("Attempting to load email credentials exclusively from environment variables...")
    
    mail_host_env = os.environ.get('MAIL_HOST') or os.environ.get('MAIL_SERVER')
    mail_port_env = os.environ.get('MAIL_PORT')
    username_from_env = os.environ.get('MAIL_USERNAME')
    password_from_env = os.environ.get('MAIL_PASSWORD')

    logger.info(
        f"Read from env: MAIL_HOST/MAIL_SERVER='{mail_host_env}'"
        f" (type: {type(mail_host_env)})"
    )
    logger.info(f"Read from env: MAIL_PORT='{mail_port_env}' (type: {type(mail_port_env)})")
    logger.info(f"Read from env: MAIL_USERNAME='{username_from_env}' (type: {type(username_from_env)})")
    
    password_status = "is set and not empty" if password_from_env else \
                      ("is set but empty" if password_from_env == "" else "is not set (None)")
    logger.info(f"Read from env: MAIL_PASSWORD status: {password_status}")

    # Check if all essential variables are present and non-empty
    if mail_host_env and mail_port_env and username_from_env and password_from_env:
        logger.info(f"Successfully loaded all required email credentials from environment variables. Username: '{username_from_env}'")
        return {
            'MAIL_HOST': mail_host_env,
            'MAIL_PORT': mail_port_env, # Will be converted to int by smtplib or sending function
            'MAIL_USERNAME': username_from_env,
            'MAIL_PASSWORD': password_from_env
        }
    else:
        missing_or_empty = []
        if not mail_host_env: missing_or_empty.append("MAIL_HOST/MAIL_SERVER")
        if not mail_port_env: missing_or_empty.append("MAIL_PORT")
        if not username_from_env: missing_or_empty.append("MAIL_USERNAME")
        if not password_from_env: missing_or_empty.append("MAIL_PASSWORD")
        
        logger.error(f"Failed to load one or more required email credentials from environment variables. Missing/empty: {', '.join(missing_or_empty)}")
        return {}

def format_signal_for_report(signal_data, title_prefix=""):
    """Format a signal dictionary into a readable string for the report"""
    if not signal_data:
        return "No signal data available."
    
    lines = []
    if title_prefix:
        lines.append(f"--- {title_prefix} ---")
    
    if not signal_data.get('signal_found'):
        lines.append(f"  {signal_data.get('message', 'No signal found.')}")
        return "\n".join(lines)
    
    # Format signal details
    market_segment_info = ""
    if signal_data.get('market_segment') != 'N/A' and title_prefix.startswith("Overall"):
        market_segment_info = f" (Market: {signal_data.get('market_segment')})"
    
    lines.append(f"  Symbol: {signal_data.get('symbol', 'N/A')}{market_segment_info}")
    lines.append(f"  Date: {signal_data.get('date', 'N/A')}")
    lines.append(f"  Setup Type: {signal_data.get('setup_type', 'N/A')} (Tier: {signal_data.get('tier', 'N/A')})")
    
    if 'strategy_score' in signal_data:
        lines.append(f"  Strategy Score: {signal_data.get('strategy_score', 0.0):.3f}")
    
    # Historical data
    hist_strength = signal_data.get('historical_strength_score')
    hist_win_rate = signal_data.get('historical_win_rate')
    hist_trades = signal_data.get('historical_total_trades')

    if hist_strength is not None and hist_win_rate is not None and hist_trades is not None:
        lines.append(
            f"  Historical Strength: {hist_strength:.2f} (Win Rate: {hist_win_rate:.2%}, Trades: {hist_trades})"
        )
    
    # Pricing data
    if 'latest_close' in signal_data:
        lines.append(f"  Current Close: {signal_data.get('latest_close', 0.0):.2f}")
    
    if 'entry_price' in signal_data:
        lines.append(f"  Potential Entry: ~{signal_data.get('entry_price', 0.0):.2f}")
    
    if 'stop_loss_price' in signal_data:
        lines.append(f"  Potential Stop-Loss: {signal_data.get('stop_loss_price', 0.0):.2f}")
    
    if 'target_price' in signal_data:
        lines.append(f"  Potential Target: {signal_data.get('target_price', 0.0):.2f}")
    
    if 'risk_reward_ratio' in signal_data:
        lines.append(f"  Potential R:R: {signal_data.get('risk_reward_ratio', 0.0):.2f}")
    
    if 'atr' in signal_data:
        lines.append(f"  ATR: {signal_data.get('atr', 0.0):.3f}")
    
    return "\n".join(lines)

def generate_report_from_json(json_path, output_path="report.txt"):
    """Generate a formatted report from JSON data"""
    try:
        logger.info(f"Generating report from JSON: {json_path}")
        
        # Load JSON data
        with open(json_path, 'r') as f:
            signal_data = json.load(f)

        scan_date = datetime.datetime.now().date()

        def is_signal_stale(signal_dict, scan_date_obj):
            if not signal_dict or not signal_dict.get('signal_found'):
                return False  # Not stale if no signal or already marked not found

            try:
                signal_date_str = signal_dict.get('date')
                if not signal_date_str: return True # Stale if no date
                signal_date_obj = datetime.datetime.strptime(signal_date_str, '%Y-%m-%d').date()
            except ValueError:
                logger.warning(f"Could not parse date '{signal_dict.get('date')}' for signal. Considering it stale.")
                return True # Stale if date is unparseable

            age_days = (scan_date_obj - signal_date_obj).days

            latest_close = signal_dict.get('latest_close')
            stop_loss = signal_dict.get('stop_loss_price')
            is_below_stop_loss = False
            if latest_close is not None and stop_loss is not None:
                try:
                    is_below_stop_loss = float(latest_close) <= float(stop_loss)
                except (ValueError, TypeError):
                    logger.warning(f"Could not compare latest_close '{latest_close}' and stop_loss '{stop_loss}'. Assuming not below stop loss.")
                    is_below_stop_loss = False

            # Staleness conditions:
            # Safety Net: Stale if older than today (age_days > 0)
            # Fix B criteria: Stale if older than 3 days (age_days > 3) OR price is below stop loss
            stale_due_to_age_safety = age_days > 0
            # stale_due_to_fix_b = (age_days > 3) or is_below_stop_loss # Original Fix B part

            # Simplified staleness condition as per request:
            # A signal is stale if it's older than today (age_days > 0) OR if the price is below stop loss.
            # The (age_days > 3) part is removed from the OR condition with is_below_stop_loss.
            is_stale = (age_days > 0) or is_below_stop_loss

            if is_stale:
                logger.info(f"Signal for {signal_dict.get('symbol', 'N/A')} dated {signal_date_str} is STALE. Age: {age_days} days. Below SL: {is_below_stop_loss}.")
            else:
                logger.info(f"Signal for {signal_dict.get('symbol', 'N/A')} dated {signal_date_str} is VALID. Age: {age_days} days. Below SL: {is_below_stop_loss}.")

            return is_stale

        # Process overall_top_signal for staleness
        overall_signal_data = signal_data.get('overall_top_signal')
        if overall_signal_data and is_signal_stale(overall_signal_data, scan_date):
            logger.info(f"Overall top signal for {overall_signal_data.get('symbol', 'N/A')} is stale. Invalidating.")
            overall_signal_data['signal_found'] = False
            overall_signal_data['message'] = "Stale signal expired (older than today or failed validity checks). No overall top signal."
            signal_data['overall_top_signal'] = overall_signal_data # Update the main dict

        # Process segmented_signals for staleness
        segmented_signals_data = signal_data.get('segmented_signals', {})
        for segment_name, segment_data_item in segmented_signals_data.items():
            if segment_data_item and is_signal_stale(segment_data_item, scan_date):
                logger.info(f"Segment signal for {segment_name} ({segment_data_item.get('symbol', 'N/A')}) is stale. Invalidating.")
                segment_data_item['signal_found'] = False
                segment_data_item['message'] = f"Stale signal expired for {segment_name} (older than today or failed validity checks). No trade today."
                signal_data['segmented_signals'][segment_name] = segment_data_item # Update the main dict
        
        # Start building the report
        report_lines = []
        
        # Overall top signal (potentially updated)
        overall_signal = signal_data.get('overall_top_signal', {})
        overall_text = format_signal_for_report(overall_signal, "Overall Top Selected Trade Candidate for Today")
        report_lines.append(overall_text)
        report_lines.append("")  # Add a blank line
        
        # Per-segment signals (potentially updated)
        report_lines.append("\n--- Per-Segment Top Signal Summary ---\n")
        
        segmented_signals = signal_data.get('segmented_signals', {})
        for market_name, segment_data in segmented_signals.items():
            market_text = format_signal_for_report(segment_data, f"Top Signal for {market_name.upper()} Market")
            report_lines.append(market_text)
            report_lines.append("")  # Add a blank line
        
        # Add some information about signal consistency
        report_lines.append("\nNOTE: Stock signals may change between runs due to live market data updates.")
        report_lines.append("This report provides the official signals for trading decisions.")
        
        # Create the report content
        report_content = "\n".join(report_lines)
        
        # Save to file
        with open(output_path, 'w') as f:
            f.write(report_content)
        
        logger.info(f"Report successfully generated and saved to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        return False

def find_latest_signal_file(signals_dir="results/live_signals"):
    """Find the latest signal JSON file in the given directory"""
    base_path = Path(os.path.dirname(os.path.abspath(__file__))) / signals_dir
    json_files = sorted(glob.glob(str(base_path / "daily_signal_*.json")))
    
    if not json_files:
        return None
    
    # Sort by file modification time (most recent first)
    return max(json_files, key=os.path.getmtime)

def track_signal_changes(signals_dir="results/live_signals"):
    """Track signal changes and create a human-readable summary"""
    base_path = Path(os.path.dirname(os.path.abspath(__file__)))
    signals_path = base_path / signals_dir
    summary_file = signals_path / "signal_changes_summary.txt"
    
    # Find all signal files
    json_files = sorted(glob.glob(str(signals_path / "daily_signal_*.json")))
    if not json_files:
        logger.warning("No signal files found.")
        return False
    
    logger.info(f"Found {len(json_files)} signal files for tracking.")
    
    # Parse and collect basic signal data without pandas
    records = []
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            filename = os.path.basename(json_file)
            file_date = filename.replace("daily_signal_", "").replace(".json", "")
            modification_time = datetime.datetime.fromtimestamp(
                os.path.getmtime(json_file)).strftime('%Y-%m-%d %H:%M:%S')
            
            # Extract overall signal data
            overall = data.get('overall_top_signal', {})
            overall_symbol = overall.get('symbol', 'N/A')
            overall_market = overall.get('market_segment', 'N/A')
            overall_setup = overall.get('setup_type', 'N/A')
            overall_found = overall.get('signal_found', False)
            
            # Extract segment signals
            segments = data.get('segmented_signals', {})
            segment_info = {}
            
            for segment_name, segment_data in segments.items():
                segment_info[segment_name] = {
                    'symbol': segment_data.get('symbol', 'N/A'),
                    'setup': segment_data.get('setup_type', 'N/A'),
                    'found': segment_data.get('signal_found', False)
                }
            # Create record
            records.append({
                'file_date': file_date,
                'modification_time': modification_time,
                'overall_symbol': overall_symbol,
                'overall_market': overall_market,
                'overall_setup': overall_setup,
                'overall_found': overall_found,
                'segments': segment_info
            })
            
        except Exception as e:
            logger.error(f"Error parsing {json_file}: {e}")
    
    if not records:
        logger.warning("No signal records could be parsed.")
        return False
    
    # Sort by file date (most recent first)
    records.sort(key=lambda x: x['file_date'], reverse=True)
    
    # Format the summary
    summary_lines = [
        "======================================",
        "   STOCK SIGNAL TRACKING SUMMARY",
        "======================================",
        f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total signals tracked: {len(records)}",
        ""
    ]
    
    # Add the latest signals
    summary_lines.append("LATEST SIGNALS BY DATE:")
    summary_lines.append("----------------------")
    
    for record in records[:7]:  # Show last 7 days
        date_str = record['file_date']
        overall_signal = record['overall_symbol'] if record['overall_found'] else "No signal"
        
        summary_lines.append(f"{date_str}: {overall_signal} ({record['overall_market']})")
        
        # Add segment details
        segment_details = []
        for segment_name, segment_data in record['segments'].items():
            if segment_data['found']:
                segment_details.append(f"{segment_name.upper()}: {segment_data['symbol']}")
            else:
                segment_details.append(f"{segment_name.upper()}: No signal")
        
        summary_lines.append("  " + ", ".join(segment_details))
        summary_lines.append("  Generated: " + record['modification_time'])
        summary_lines.append("")
    
    # Add explanation about signal changes
    summary_lines.append("")
    summary_lines.append("NOTE: Stock signals may change between script runs due to:")
    summary_lines.append("- Live market data updates (prices, volumes change throughout the day)")
    summary_lines.append("- Algorithmic selection based on current market conditions")
    summary_lines.append("- Different tickers meeting signal criteria on different runs")
    summary_lines.append("")
    summary_lines.append("For consistent trading, use the signals from the official daily report.")
    
    # Write the summary to file
    with open(summary_file, 'w') as f:
        f.write("\n".join(summary_lines))
    
    logger.info(f"Signal tracking summary saved to {summary_file}")
    
    # Also append the tracking summary to the report
    return summary_lines

def log_environment_info():
    """Log information about the execution environment"""
    logger.info("\n===== ENVIRONMENT INFORMATION =====")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {platform.platform()}")
    logger.info(f"Hostname: {socket.gethostname()}")
    logger.info(f"Current directory: {os.getcwd()}")
    
    # Check if we're running in GitHub Actions
    if 'GITHUB_ACTIONS' in os.environ:
        logger.info("Running in GitHub Actions: YES")
        # Print some GitHub-specific environment variables
        for key in ['GITHUB_WORKFLOW', 'GITHUB_RUN_ID', 'GITHUB_REPOSITORY']:
            if key in os.environ:
                logger.info(f"{key}: {os.environ.get(key)}")
    else:
        logger.info("Running in GitHub Actions: NO")

def send_report_email(report_file_path, credentials, recipient_email="katar.fhm@gmail.com"):
    """Send the report via email using credentials from the environment or .secrets"""
    logger.info("\\n===== SENDING REPORT EMAIL =====")
    log_environment_info() # Log environment details

    mail_server = credentials.get('MAIL_HOST')
    mail_port_str = credentials.get('MAIL_PORT')
    sender_email = credentials.get('MAIL_USERNAME')
    password = credentials.get('MAIL_PASSWORD')

    if not all([mail_server, mail_port_str, sender_email, password]):
        missing = [k for k,v in {'MAIL_HOST': mail_server, 'MAIL_PORT': mail_port_str, 
                                'MAIL_USERNAME': sender_email, 'MAIL_PASSWORD': password}.items() if not v]
        logger.error(f"Missing one or more email credentials: {', '.join(missing)}. Cannot send report.")
        return False

    try:
        mail_port = int(mail_port_str) # Convert port to integer
    except ValueError:
        logger.error(f"Invalid MAIL_PORT: '{mail_port_str}'. Must be an integer.")
        return False

    logger.info(f"Mail server: {mail_server}")
    logger.info(f"Mail port: {mail_port}")
    logger.info(f"Mail username: {sender_email}")
    # Do not log password directly
    logger.info(f"Recipient: {recipient_email}")
    logger.info(f"Report file: {report_file_path}")

    try:
        with open(report_file_path, 'r') as f:
            report_content = f.read()
        logger.info(f"Report content loaded ({len(report_content)} chars)")

        msg = MIMEMultipart()
        msg['From'] = f"Rojhak Azadi <{sender_email}>"
        msg['To'] = recipient_email
        
        today_date = datetime.datetime.now().strftime("%Y-%m-%d")
        msg['Subject'] = f"Daily Trading Signal Report - {today_date}"
        
        msg.attach(MIMEText(report_content, 'plain'))

        logger.info("Creating SSL context...")
        context = ssl.create_default_context()

        logger.info(f"Connecting to {mail_server}:{mail_port}...")
        
        # Determine connection type based on port
        if mail_port == 465: # SSL
            logger.info("Using SMTP_SSL for port 465.")
            with smtplib.SMTP_SSL(mail_server, mail_port, context=context) as server:
                logger.info("Attempting to login...")
                server.login(sender_email, password)
                logger.info("Login successful. Sending email...")
                server.sendmail(sender_email, recipient_email, msg.as_string())
                logger.info("Email sent successfully!")
        elif mail_port == 587: # TLS
            logger.info("Using SMTP with starttls for port 587.")
            with smtplib.SMTP(mail_server, mail_port) as server:
                logger.info("Starting TLS...")
                server.starttls(context=context)
                logger.info("TLS started. Attempting to login...")
                server.login(sender_email, password)
                logger.info("Login successful. Sending email...")
                server.sendmail(sender_email, recipient_email, msg.as_string())
                logger.info("Email sent successfully!")
        else:
            logger.error(f"Unsupported mail port: {mail_port}. Please use 465 (SSL) or 587 (TLS).")
            return False
            
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"❌ SMTP Authentication Error: {e}")
        logger.error("Please check your MAIL_USERNAME and MAIL_PASSWORD (App Password if using Gmail).")
    except smtplib.SMTPConnectError as e:
        logger.error(f"❌ SMTP Connect Error: {e}")
        logger.error(f"Failed to connect to {mail_server}:{mail_port}. Check MAIL_HOST and MAIL_PORT.")
    except smtplib.SMTPServerDisconnected as e:
        logger.error(f"❌ SMTP Server Disconnected: {e}")
    except socket.gaierror as e:
        logger.error(f"❌ Socket/Address Error: {e}. Check if MAIL_HOST ('{mail_server}') is correct and reachable.")
    except ssl.SSLError as e:
        logger.error(f"❌ Error sending email: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        if "WRONG_VERSION_NUMBER" in str(e) and mail_port == 587:
            logger.error("This might indicate an issue with STARTTLS. Ensure the server supports TLS on this port.")
        elif "WRONG_VERSION_NUMBER" in str(e) and mail_port == 465:
             logger.error("This might indicate an issue with SSL. Ensure the server expects SSL on this port.")
    except Exception as e:
        logger.error(f"❌ An unexpected error occurred: {e}")
        logger.error(f"Error type: {type(e).__name__}")
    
    return False

def enhanced_report_workflow(json_path=None, output_path="report.txt", send_email=True):
    """
    Complete report workflow:
    1. Find latest signal file if not provided
    2. Generate report
    3. Track signal changes
    4. Send email
    """
    logger.info("Starting enhanced report workflow...")
    
    # Find the latest signal file if not provided
    if not json_path:
        json_path = find_latest_signal_file()
        if not json_path:
            logger.error("No signal file found.")
            return False
    
    logger.info(f"Using signal file: {json_path}")
    
    # Generate the report
    report_success = generate_report_from_json(json_path, output_path)
    if not report_success:
        logger.error("Failed to generate report.")
        return False
    
    # Track signal changes
    signal_tracking = track_signal_changes()
    
    # If we have signal tracking info, add it to the report
    if signal_tracking:
        with open(output_path, 'a') as f:
            f.write("\n\n" + "="*50 + "\n")
            f.write("SIGNAL CHANGE TRACKING\n")
            f.write("="*50 + "\n\n")
            f.write("\n".join(signal_tracking))
    
    # Send email if requested
    if send_email:
        email_success = send_report_email(output_path)
        if not email_success:
            logger.error("Failed to send email.")
            return False
    
    logger.info("Enhanced report workflow completed successfully.")
    return True

def main():
    """Main function"""
    logger.info(f"enhanced_report.py called with arguments: {sys.argv}")

    # Special case for email-only mode
    if len(sys.argv) == 3 and sys.argv[1].lower() == 'email-only':
        report_path = sys.argv[2]
        logger.info(f"Email-only mode activated: Sending existing report at {report_path}")
        credentials = load_email_credentials()
        if not credentials:
            logger.error("Failed to load credentials for email-only mode.")
            sys.exit(1)
        success = send_report_email(report_path, credentials)
        logger.info(f"Email-only mode finished. Success: {success}")
        sys.exit(0 if success else 1)
    elif len(sys.argv) == 2 and sys.argv[1].lower() == 'email-only':
        logger.error("Email-only mode requires a report file path argument.")
        logger.info("Usage: python enhanced_report.py email-only [report_file_path]")
        sys.exit(1)
    
    # Normal operation mode
    logger.info("Proceeding with normal operation mode (report generation and optional email).")
    if len(sys.argv) < 2:
        logger.info("Usage: python enhanced_report.py [signal_json_file] [output_report_file] [send_email=yes/no]")
        logger.info("       python enhanced_report.py email-only [report_file]")
        logger.info("  If signal_json_file is not provided, latest file will be used.")
        logger.info("  If output_report_file is not provided, 'report.txt' will be used.")
        logger.info("  If send_email is not provided, email will be sent.")
        logger.info("  Use 'email-only' as first argument to only send an existing report.")
        
        json_path = find_latest_signal_file()
        if not json_path:
            logger.error("No signal file found and none provided.")
            return 1
        
        output_path = "report.txt"
        send_email = True
    else:
        json_path = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else "report.txt"
        send_email = True
        if len(sys.argv) > 3:
            send_email = sys.argv[3].lower() not in ('no', 'false', '0')
    
    # Run the workflow
    success = enhanced_report_workflow(json_path, output_path, send_email)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
