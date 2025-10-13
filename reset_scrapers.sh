#!/bin/bash
# Force process today's announcements by resetting baselines

echo "🔄 Resetting announcement baselines to process today's announcements..."

# Remove existing baseline files
if [ -f "data/latest_announcement_bse_scraper.json" ]; then
    echo "📄 Removing BSE baseline file"
    rm data/latest_announcement_bse_scraper.json
fi

if [ -f "data/latest_announcement_nse_scraper.json" ]; then
    echo "📄 Removing NSE baseline file"  
    rm data/latest_announcement_nse_scraper.json
fi

echo "🚀 Restarting scraper containers..."
docker-compose -f docker-compose.redis.yml restart bse-scraper nse-scraper

echo "✅ Scrapers will now process all current announcements"
echo "📊 Monitor progress with: docker logs -f backfin-bse-scraper"