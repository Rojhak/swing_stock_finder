# Daily Trading Signal Generator

## Overview

This project automates the process of identifying potential trading signals by running the Python script `scripts/high_current.py`. The script analyzes market data to find assets that meet specific criteria, generating a daily report of these signals.

## Automated Daily Reports

A GitHub Actions workflow is configured to execute the `scripts/high_current.py` script automatically every day.

-   **Workflow Definition**: The automation logic is defined in the workflow file located at `.github/workflows/daily_report.yml`.
-   **Daily Email**: Upon successful execution and generation of a report, the workflow sends the report content via email to a predefined recipient.

## Email Notification Setup

For the automated email notifications to function correctly, specific GitHub secrets must be configured in the repository. These secrets are used by the workflow to authenticate with the email server and send the report.

To set up these secrets:

1.  Navigate to your repository's **Settings** tab.
2.  Go to **Secrets and variables > Actions**.
3.  Click on **New repository secret** for each of the following:

    *   `MAIL_SERVER`: The address of your SMTP server (e.g., `smtp.gmail.com`).
    *   `MAIL_USERNAME`: The username for the email account that will send the reports (e.g., `your_email@example.com`).
    *   `MAIL_PASSWORD`: The password or an app-specific password for the email account. Consult your email provider's documentation for generating app-specific passwords if you use 2-Factor Authentication (recommended).

**Important**: Without these secrets being correctly configured, the email sending step in the GitHub Actions workflow will fail, and no daily reports will be delivered via email.

## Script Details

The core logic for generating trading signals resides in the main script.

-   **Main Script**: `scripts/high_current.py`
-   **Dependencies**: The script relies on the following Python libraries:
    -   `yfinance`
    -   `pandas`
    -   `numpy`
    -   `tqdm`
-   **Required Data Files**: The script requires the following data files to be present in the repository:
    -   `data/euro_tickers.csv`
    -   `data/sp400_tickers.csv`
    -   `data/sp500_tickers.csv`
    -   `results/long_term_historical_perf/historical_symbol_performance_long_term.csv`

Ensure these dependencies are available in the environment where the script is run (they are handled by the GitHub Actions workflow) and that the data files are correctly placed within the repository.
