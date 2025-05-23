# Database Migration Plan for Trade Tracking

## Current System Limitations
The current CSV-based trade tracking system has several limitations:
1. **Concurrency Issues**: Multiple processes writing to the same file can lead to corruption
2. **Performance**: As the number of trades grows, CSV operations become slower
3. **Data Integrity**: No enforcement of constraints or data types
4. **Querying Capability**: Limited ability to perform complex queries
5. **Backup and Recovery**: Manual file-based backup is required

## Proposed Solution
Convert the trade tracking system to use SQLite, which provides:
1. **File-based Database**: No need for a separate server
2. **ACID Compliance**: Ensures data integrity and transaction safety
3. **SQL Query Support**: Full SQL query capabilities for reporting
4. **Easy Integration**: Python has built-in SQLite support

## Implementation Steps

### 1. Database Schema Design
```sql
CREATE TABLE trades (
    trade_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    entry_date TEXT NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss_price REAL NOT NULL,
    target_price REAL NOT NULL,
    risk_reward_ratio REAL,
    atr_at_entry REAL,
    trade_type TEXT NOT NULL,
    source_signal_date TEXT,
    status TEXT NOT NULL,
    current_price REAL,
    unrealized_pnl REAL,
    exit_date TEXT,
    exit_price REAL,
    realized_pnl REAL,
    exit_reason TEXT,
    holding_period INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_entry_date ON trades(entry_date);
```

### 2. Create db_manager.py Module
Develop a new module replacing the CSV-based operations:
- Connection handling
- CRUD operations for trades
- Migration utilities

### 3. Migration Process
1. Create the database schema
2. Import existing CSV data
3. Validate data integrity
4. Switch code paths to use the database

### 4. Function Mapping
| Current Function | Database Equivalent |
|------------------|---------------------|
| _get_trades_df_and_ensure_header() | get_trades_db_connection() |
| add_tracked_signal() | add_tracked_signal_db() |
| close_trade() | close_trade_db() |
| update_active_trades() | update_active_trades_db() |

### 5. Implementation Timeline
1. Week 1: Development of db_manager.py and schema
2. Week 2: Update of tracking_manager.py to use the database
3. Week 3: Testing and validation
4. Week 4: Deployment and monitoring

### 6. Benefits
- **Reliability**: Concurrent access handling
- **Performance**: Faster for large datasets
- **Reporting**: Advanced SQL queries for analytics 
- **Data Integrity**: Type enforcement and constraints
- **Future-proofing**: Easier migration to other databases if needed

### 7. Additional Considerations
- Add automated database backups
- Consider adding more indices based on query patterns
- Add database migration scripts for version control
- Implement connection pooling for multi-process usage
