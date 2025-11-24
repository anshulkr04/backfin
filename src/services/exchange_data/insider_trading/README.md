# Insider Trading Data Management

Unified insider trading data collection system that scrapes data from both NSE and BSE exchanges, deduplicates records, and uploads directly to the database.

## Overview

This system:
1. **Collects** insider trading data from NSE (API) and BSE (web scraping)
2. **Deduplicates** records based on `sec_name` and `person_name` (BSE data is preferred when duplicates exist)
3. **Uploads** directly to the `insider_trading` table in Supabase

## Usage

### Run manually:
```bash
cd /Users/anshulkumar/backfin/src/services/exchange_data/insider_trading
python3 insider_trading_detector.py
```

### Run as cronjob:
```bash
# Add to crontab for daily execution at 6 PM IST
0 18 * * * cd /Users/anshulkumar/backfin/src/services/exchange_data/insider_trading && python3 insider_trading_detector.py >> /var/log/insider_trading.log 2>&1
```

## Features

- **NSE Data Collection**: Uses REST API with proper session establishment
- **BSE Data Collection**: Uses Selenium WebDriver to download CSV
- **Deduplication**: Smart deduplication by company name + person name, preferring BSE data
- **Direct Upload**: No verification queue - data goes straight to the database
- **Database Trigger**: The `trigger_update_insider_trading_symbol` automatically populates the `symbol` field
- **Automatic Cleanup**: Temporary CSV/JSON files are deleted after successful upload

## Data Flow

```
┌─────────────┐        ┌─────────────┐
│  NSE API    │        │  BSE Web    │
│  (JSON)     │        │  (CSV)      │
└──────┬──────┘        └──────┬──────┘
       │                      │
       ├──────────┬───────────┤
                  │
                  ▼
       ┌─────────────────────┐
       │  Data Processing    │
       │  & Normalization    │
       └──────────┬──────────┘
                  │
                  ▼
       ┌─────────────────────┐
       │   Deduplication     │
       │  (sec_name +        │
       │   person_name)      │
       └──────────┬──────────┘
                  │
                  ▼
       ┌─────────────────────┐
       │  Upload to Database │
       │  (insider_trading)  │
       └─────────────────────┘
```

## Database Schema

The data is uploaded to the `insider_trading` table:

- **sec_code**: Security code (BSE uses sec_code, NSE uses symbol - trigger handles this)
- **sec_name**: Company name (used for deduplication)
- **person_name**: Name of insider (used for deduplication)
- **person_cat**: Category of person (Promoter, Director, etc.)
- **pre_sec_num/pct**: Holdings before transaction
- **trans_sec_num/value/type**: Transaction details
- **post_sec_num/pct**: Holdings after transaction
- **date_from/to/intimation**: Transaction dates
- **mode_acq**: Mode of acquisition
- **exchange**: NSE or BSE
- **symbol**: Stock symbol (auto-populated by database trigger)

## Environment Variables

Required in `.env`:
```
SUPABASE_URL2=your_supabase_url
SUPABASE_KEY2=your_supabase_key
```

## Dependencies

- requests
- pandas
- numpy
- selenium
- webdriver-manager
- supabase
- python-dotenv

## Deduplication Logic

When the same transaction appears in both NSE and BSE data:
- Deduplication key: `sec_name + person_name + date_from + date_to + trans_sec_num`
- **BSE data is preferred** over NSE data
- Case-insensitive matching on company and person names

## Error Handling

- NSE API failures are logged but don't stop BSE collection
- BSE scraping failures are logged but don't stop the process
- Upload failures are logged with sample problematic records
- Temporary files are cleaned up even on errors

## Logs

The system logs:
- Data collection progress
- Record counts from each source
- Deduplication statistics
- Upload status and any errors
- Cleanup status

## Notes

- **No verification queue**: Data is directly uploaded (unlike other data types)
- **Date format**: Defaults to today's date (DD-MM-YYYY)
- **Batch upload**: Records are uploaded in batches of 100
- **Automatic symbol population**: Database trigger handles symbol mapping
