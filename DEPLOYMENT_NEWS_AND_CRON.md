# Deployment Guide: News Article Generation + Cron Jobs

## Overview

This deploys:
1. **Article Generation Worker** — Redis BRPOP consumer that generates news articles from corporate filings using Grok (xai-sdk)
2. **Cron Manager** — APScheduler-based job scheduler for scraping, cleanup, etc.
3. **V2 Corporate Filings API** — Authenticated endpoint with watchlist/read-unread/marketcap filters
4. **Frontend** — Updated market-feed and dashboard with V2 API + watchlist filtering

---

## Step 1: Run SQL Migrations in Supabase

Go to **Supabase Dashboard → SQL Editor** and run these in order:

### 1a. V2 Corporate Filings RPC function
```
File: migrations/v2_corporate_filings_api.sql
```
This creates the `get_corporate_filings_v2` Postgres function used by the V2 API.

### 1b. News Articles table
```
File: migrations/news_articles_schema.sql
```
This creates:
- `news_articles` table (with UUID `corp_id` FK to `corporatefilings`)
- 12 indexes for fast lookups (slug, isin, symbol, category, sentiment, etc.)
- RLS policies (public read, service-role insert/update)
- Auto `updated_at` trigger

**Verify after running:**
```sql
SELECT count(*) FROM information_schema.tables WHERE table_name = 'news_articles';
-- Should return 1
```

---

## Step 2: Add Environment Variables

Add `XAI_API_KEY` to your environment:

### For Docker (.env file):
```bash
echo 'XAI_API_KEY=your-xai-api-key-here' >> .env
```

### For Kubernetes (secret):
```bash
kubectl -n backfin create secret generic backfin-secrets \
  --from-literal=XAI_API_KEY=your-xai-api-key-here \
  --dry-run=client -o yaml | kubectl apply -f -
```
Or edit the existing secret:
```bash
kubectl -n backfin edit secret backfin-secrets
# Add XAI_API_KEY (base64 encoded)
```

The worker also needs these existing env vars (already in .env / backfin-secrets):
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `REDIS_HOST`
- `REDIS_PORT`

---

## Step 3: Deploy the Article Generation Worker

### Option A: Docker Compose
```bash
# Build and start the article worker
docker compose -f docker-compose.redis.yml build article-worker
docker compose -f docker-compose.redis.yml up -d article-worker
```

### Option B: Kubernetes
```bash
# Build the Docker image on the VM
docker build -t backfin/article-worker:latest -f docker/Dockerfile.article-worker .

# Apply the updated workers.yaml (includes article-worker deployment)
kubectl apply -f k8s/workers.yaml

# Verify it's running
kubectl -n backfin get pods -l app=article-worker
kubectl -n backfin logs -l app=article-worker --tail=50
```

---

## Step 4: Deploy Updated Supabase Worker

The `ephemeral_supabase_worker.py` now enqueues article generation jobs after inserting filings.

**If using Docker Compose**, this should already be running. Just restart it:
```bash
docker compose -f docker-compose.redis.yml restart worker-spawner
```

**If using Kubernetes**, rebuild and deploy:
```bash
docker build -t backfin/supabase-worker:latest -f docker/Dockerfile.supabase-worker .
kubectl -n backfin rollout restart deployment/supabase-worker
```

---

## Step 5: Deploy the Cron Manager

```bash
# Docker Compose
docker compose -f docker-compose.redis.yml build cron-manager
docker compose -f docker-compose.redis.yml up -d cron-manager

# Kubernetes
docker build -t backfin/cron-manager:latest -f docker/Dockerfile.cron-manager .
kubectl apply -f k8s/workers.yaml
kubectl -n backfin rollout restart deployment/cron-manager
```

---

## Step 6: Deploy Updated API

The API already has the V2 endpoint. Just restart to pick up any changes:

```bash
# Docker Compose
docker compose -f docker-compose.redis.yml restart api

# Kubernetes
kubectl -n backfin rollout restart deployment/api-server
```

---

## Step 7: Deploy Frontend

```bash
cd frontend
npm run build
# Deploy the build output to your hosting (Vercel, etc.)
```

If using Vercel, just push to the branch and it auto-deploys.

---

## Verification Checklist

### Check Article Worker is Running
```bash
# Docker
docker logs backfin-article-worker --tail=20

# Kubernetes
kubectl -n backfin logs -l app=article-worker --tail=20
```
Should show: `Article generation worker started. Listening on backfin:queue:article_generation`

### Check Redis Queue
```bash
# Connect to Redis and check queue length
redis-cli -h <REDIS_HOST> LLEN backfin:queue:article_generation
```

### Check News Articles Table
```sql
-- In Supabase SQL Editor
SELECT count(*) FROM news_articles;
SELECT * FROM news_articles ORDER BY published_at DESC LIMIT 5;
```

### Check V2 API
```bash
curl -H "Authorization: Bearer <YOUR_TOKEN>" \
  "https://api.marketwire.ai/api/v2/corporate_filings?page=1&page_size=5&watchlist=true"
```

### Check Frontend
1. Open dashboard — watchlist dropdown should filter announcements
2. Open market-feed — watchlist dropdown + read/unread toggle should work
3. Selecting "All Watchlists" uses server-side filtering
4. Selecting a specific watchlist filters by that watchlist's ISINs

---

## Architecture Flow

```
BSE/NSE Scrapers
    ↓ (LPUSH to Redis)
Worker Spawner → Ephemeral Supabase Worker
    ↓ (inserts to corporatefilings)
    ↓ (LPUSH ArticleGenerationJob to Redis)
Article Generation Worker (BRPOP)
    ↓ (calls Grok API via xai-sdk)
    ↓ (inserts to news_articles table)
    
Frontend → V2 API → Supabase RPC → corporatefilings + watchlist filtering
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `XAI_API_KEY not set` | Add to .env or k8s secret (Step 2) |
| `relation "news_articles" does not exist` | Run SQL migration (Step 1b) |
| `function get_corporate_filings_v2 does not exist` | Run SQL migration (Step 1a) |
| Article worker not consuming jobs | Check Redis connection, verify REDIS_HOST/PORT |
| No articles generated | Check if `is_article_worthy()` passes — needs valid category + ai_summary > 30 chars |
| Frontend shows 401 | User not authenticated — check auth token |
| Watchlist filter returns empty | Check if watchlist has ISINs assigned |
