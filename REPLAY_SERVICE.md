# Backfin Replay Service

## Overview

The replay service continuously monitors for unprocessed announcements and unsent data, ensuring no announcements are missed. It runs every minute and processes both AI analysis and Supabase uploads.

## Features

- **Continuous Monitoring**: Checks every 60 seconds for unprocessed data
- **AI Processing**: Processes PDFs that weren't analyzed properly
- **Supabase Upload**: Ensures all processed data reaches Supabase
- **Smart Category Handling**: Skips AI for "Procedural/Administrative" categories
- **Adaptive Intervals**: Increases check interval when no work is found
- **Multi-day Coverage**: Checks last 7 days by default
- **Graceful Shutdown**: Handles interrupts properly
- **Comprehensive Logging**: Tracks all operations

## Usage

### Docker Compose (Recommended)

```bash
# Start both main app and replay service
docker-compose up -d
exit

# View replay service logs
docker-compose logs -f replay-service

# Stop services
docker-compose down
```

### Standalone Script

```bash
# Continuous mode (default - runs forever)
python replay.py --continuous

# Single date processing
python replay.py --date 2025-10-04

# Custom intervals and settings
python replay.py --continuous --interval 30 --days-back 3 --batch 100

# Disable AI processing
python replay.py --continuous --no-ai
```

### Dedicated Service Script

```bash
# Run as dedicated service with logging
python replay_service.py
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `--continuous` | False | Run in continuous mode |
| `--interval` | 60 | Check interval in seconds |
| `--days-back` | 7 | Number of days to check for unprocessed data |
| `--batch` | 200 | Number of rows to process per cycle |
| `--retries` | 3 | Number of retries for failed operations |
| `--no-ai` | False | Disable AI processing |

## How It Works

1. **Scans Database**: Looks for rows where:
   - `ai_processed = 0` (needs AI analysis)
   - `sent_to_supabase = 0` (needs upload)

2. **AI Processing**: For unprocessed announcements:
   - Downloads PDFs if available
   - Processes with Gemini API
   - Updates local database with results
   - Handles "Procedural/Administrative" categories

3. **Supabase Upload**: For unsent data:
   - Uploads processed announcements
   - Handles financial and investor data
   - Manages duplicate entries gracefully

4. **Adaptive Behavior**:
   - Normal interval when work is found
   - Longer intervals during quiet periods
   - Comprehensive error handling and recovery

## Docker Services

The `docker-compose.yml` now includes two services:

### `backfin` (Main Application)
- Runs the web server on port 8000
- Handles live scraping and API endpoints

### `replay-service` (Background Processor)
- Continuously processes unprocessed data
- Runs independently of the main app
- Automatically restarts if it fails

## Monitoring

### View Logs
```bash
# All services
docker-compose logs -f

# Just replay service
docker-compose logs -f replay-service

# Main app only
docker-compose logs -f backfin
```

### Check Status
```bash
# See running containers
docker-compose ps

# Check resource usage
docker stats
```

## Production Considerations

1. **Resource Usage**: The replay service is lightweight and checks adaptively
2. **Data Persistence**: Both services share the same data volume
3. **Error Recovery**: Service automatically recovers from transient failures
4. **Scaling**: Can run multiple replay services for different date ranges if needed

## Troubleshooting

### Common Issues

1. **AI Processing Fails**
   - Check Gemini API key in environment variables
   - Verify network connectivity
   - Check rate limits

2. **Supabase Upload Fails**
   - Verify Supabase credentials
   - Check network connectivity
   - Review duplicate key errors (usually harmless)

3. **No Data Found**
   - Normal behavior - service adapts interval automatically
   - Check if main scraper is running
   - Verify date range settings

### Debug Mode

Run with more verbose logging:
```bash
# Enable debug logging
PYTHONPATH=. python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from replay import run_continuous_replay
run_continuous_replay(check_interval=10, days_back=1)
"
```

## Integration with Main Scraper

The replay service complements the main scraper (`new_scraper.py`):

- **Main Scraper**: Processes new announcements in real-time
- **Replay Service**: Catches any missed or failed processing
- **Shared Database**: Both use the same local SQLite database
- **No Conflicts**: Services coordinate through database flags

This ensures 100% coverage of all announcements with redundant processing capabilities.