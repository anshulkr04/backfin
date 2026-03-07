# MarketWire News Site — Roadmap

> **Subdomain:** `news.marketwire.app`  
> **Framework:** Astro.js (SSR/SSG, SEO-first)  
> **Goal:** Free, public news site auto-generated from corporate filings → lead gen for the paid MarketWire platform.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Supabase (shared DB)                      │
│  corporatefilings + stocklistdata + articles table           │
└────────────┬────────────────────────────────────┬───────────┘
             │                                    │
    ┌────────▼────────┐                  ┌────────▼────────┐
    │  MarketWire App  │                 │  News Site       │
    │  (Next.js)       │                 │  (Astro.js)      │
    │  app.marketwire  │                 │  news.marketwire │
    │  Paid product    │                 │  Free / public   │
    └─────────────────┘                  └─────────────────┘
```

### Why Astro.js
- Static-first with on-demand SSR — ideal for SEO content sites
- Zero JS shipped by default → fastest possible page loads
- Built-in sitemap, RSS, image optimization
- Island architecture for interactive components (search, filters)
- Markdown/MDX native — great for article content
- Integrates with any backend API (Supabase direct or REST)

---

## 2. Content Tiers (3-Layer System)

| Tier | Name | Description | Volume/Day |
|------|------|-------------|------------|
| **Tier 1** | Full Article | AI-generated ~300-word article with key takeaways, context | ~50-80 |
| **Tier 2** | Wire Item | 2-3 sentence summary with link to PDF | ~1,500-2,000 |
| **Tier 3** | Skip | Procedural/admin filings, not published | ~300-500 |

### Article Generation Pipeline
```
corporatefilings (existing AI summary)
   │
   ▼
classify_publish_tier()  ──► Tier 2/3 → Wire item or skip
   │
   Tier 1
   ▼
Second lightweight prompt (GPT-4o-mini / Gemini Flash)
   │
   Input: { headline, ai_summary, category, sentiment, companyname }
   │
   Output: {
     article_headline,
     article_meta_description,
     article_body (300 words, journalist tone),
     key_takeaways[] (3-5 bullets)
   }
   │
   Cost: ~$0.003/article → $5-12/day
```

---

## 3. Publish Tier Classification

### 3-Layer Classification System

**Layer 1: Automatic Rules (deterministic)**
| Category | Company Tier | Extra Condition | → Publish Tier |
|----------|-------------|-----------------|----------------|
| Financial Results | Any | — | Tier 1 (Full Article) |
| Mergers/Acquisitions | Any | — | Tier 1 |
| Fundraise (QIP/Rights/Pref) | Large/Mid Cap | — | Tier 1 |
| New Order | Any | Value > ₹100 Cr | Tier 1 |
| Buyback / Bonus / Stock Split | Any | — | Tier 1 |
| Insider Trading (significant) | Large Cap | Value > ₹10 Cr | Tier 1 |
| Credit Rating | Large/Mid Cap | — | Tier 2 (Wire) |
| Change in KMP | Large Cap only | — | Tier 1 |
| Procedural/Administrative | Any | — | Tier 3 (Skip) |
| Everything else | — | — | Tier 2 (Wire) |

**Layer 2: Company Importance Scoring**
| Tier | Definition | Count |
|------|-----------|-------|
| `nifty50` | Nifty 50 components | ~50 |
| `nifty500` | Nifty 500 components | ~500 |
| `large_cap` | Market cap > ₹20,000 Cr | ~200 |
| `mid_cap` | Market cap ₹5,000-20,000 Cr | ~300 |
| `small_cap` | Market cap < ₹5,000 Cr | Rest |

**Layer 3: Admin Override**
- Admin can manually set `publish_tier` on any filing
- Override persists and won't be recalculated

---

## 4. Database Schema Changes

### New columns on `corporatefilings` table
```sql
ALTER TABLE corporatefilings ADD COLUMN IF NOT EXISTS article_headline text;
ALTER TABLE corporatefilings ADD COLUMN IF NOT EXISTS article_body text;
ALTER TABLE corporatefilings ADD COLUMN IF NOT EXISTS article_slug text;
ALTER TABLE corporatefilings ADD COLUMN IF NOT EXISTS article_meta_desc text;
ALTER TABLE corporatefilings ADD COLUMN IF NOT EXISTS article_category text;
ALTER TABLE corporatefilings ADD COLUMN IF NOT EXISTS article_subcategory text;
ALTER TABLE corporatefilings ADD COLUMN IF NOT EXISTS publish_tier text; -- 'full_article', 'wire', 'skip'
ALTER TABLE corporatefilings ADD COLUMN IF NOT EXISTS is_published boolean DEFAULT false;
ALTER TABLE corporatefilings ADD COLUMN IF NOT EXISTS article_stale boolean DEFAULT false;
ALTER TABLE corporatefilings ADD COLUMN IF NOT EXISTS article_manually_edited boolean DEFAULT false;
ALTER TABLE corporatefilings ADD COLUMN IF NOT EXISTS article_generated_at timestamptz;
ALTER TABLE corporatefilings ADD COLUMN IF NOT EXISTS article_published_at timestamptz;
```

### New columns on `stocklistdata` table
```sql
ALTER TABLE stocklistdata ADD COLUMN IF NOT EXISTS market_cap numeric;
ALTER TABLE stocklistdata ADD COLUMN IF NOT EXISTS company_tier text; -- 'nifty50', 'nifty500', 'large_cap', 'mid_cap', 'small_cap', 'micro_cap', 'nano_cap'
```

---

## 5. Category Architecture

### Launch Categories (Market News subcategories only)
- **Results & Earnings** — Financial Results, Concall Transcripts
- **Deals & M&A** — Mergers/Acquisitions, Joint Ventures, Divestitures
- **Fundraising** — QIP, Rights Issue, Preferential Issue, Buyback
- **Orders & Expansion** — New Order, Expansion, New Product
- **Corporate Changes** — Bonus/Stock Split, Change in KMP, Name Change, Demerger
- **Regulatory** — Credit Rating, USFDA, Regulatory Approvals, PLI Scheme
- **Investor Activity** — Investor/Analyst Meet, Investor Presentation

### URL Structure
```
/                                    → Homepage (latest articles + wire)
/results-earnings/                   → Category page
/results-earnings/tcs-q3-fy26-...   → Article page
/wire/                               → All wire items (reverse chron)
/company/reliance/                   → Company page (all articles for RELIANCE)
/search?q=...                        → Search
/sitemap.xml                         → Google News sitemap
/rss.xml                             → RSS feed
```

---

## 6. Page Designs

### Homepage
```
┌──────────────────────────────────────────────────┐
│  MarketWire News  [Categories ▾]  [Search 🔍]   │
├──────────────────────────────────────────────────┤
│  BREAKING / LATEST                               │
│  ┌────────────────────────────────────────────┐  │
│  │ [Featured Article — Full Width Hero Card]  │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ Article  │ │ Article  │ │ Article  │        │
│  │ Card     │ │ Card     │ │ Card     │        │
│  └──────────┘ └──────────┘ └──────────┘        │
│                                                  │
│  LIVE WIRE ─────────────────────────────────── │
│  • HDFC Bank: Board approves ₹2,000 Cr...  2m │
│  • TCS wins $150M deal with European...     5m │
│  • SEBI issues show-cause to...             8m │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  🔔 Get alerts before anyone else        │   │
│  │  [Try MarketWire Free →]                 │   │
│  └──────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

### Article Page
```
┌──────────────────────────────────────────────────┐
│  Breadcrumb: Home > Results & Earnings           │
│                                                  │
│  TCS Reports 12% YoY Revenue Growth in Q3       │
│  Published 2 hours ago · Results & Earnings      │
│                                                  │
│  KEY TAKEAWAYS                                   │
│  • Revenue grew 12% YoY to ₹64,259 Cr          │
│  • PAT up 8% to ₹12,380 Cr                     │
│  • New order wins at $10.2B for the quarter     │
│                                                  │
│  [Article body — 300 words]                      │
│                                                  │
│  📄 Source: BSE Filing (PDF)                     │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │  Want real-time alerts for TCS filings?  │   │
│  │  MarketWire sends you notifications      │   │
│  │  within minutes, not hours.              │   │
│  │  [Start Free Trial →]                    │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  RELATED ARTICLES                                │
│  [Card] [Card] [Card]                            │
└──────────────────────────────────────────────────┘
```

---

## 7. SEO Strategy

### Technical SEO
- **Google News Sitemap** — Auto-generated, submitted to Google News
- **NewsArticle JSON-LD** — Structured data on every article page
- **RSS Feed** — Per-category and global
- **OG/Twitter Cards** — Auto-generated images with headline + company logo
- **Canonical URLs** — Prevent duplicate content issues
- **Astro built-in:** sitemap integration, image optimization, prerendering

### Content SEO
- **Slug format:** `{company}-{category}-{date-slug}` e.g. `reliance-q3-results-mar-2026`
- **Meta descriptions:** AI-generated, 155 chars, keyword-rich
- **Internal linking:** Related articles, company pages, category pages
- **Freshness signal:** Articles published within minutes of filing

---

## 8. Lead Generation Strategy

### Touchpoints
1. **In-article CTA** — "Get alerts for [Company] filings → Try MarketWire"
2. **Compared to free** — "See this filing 6 hours before it appears here"
3. **Wire page limit** — Show latest 50, "See all 2,000+ daily filings on MarketWire"
4. **Email capture** — "Get daily market digest" → nurture to paid
5. **Company page** — "Track [Company] in real-time on MarketWire"

### Conversion Funnel
```
Google Search → Article Page → CTA → MarketWire Landing Page → Free Trial → Paid
                                  ↘ Email Signup → Daily Digest → Paid
```

---

## 9. Technical Stack

```
Frontend:     Astro.js 5.x (SSR + SSG hybrid)
Styling:      Tailwind CSS 4.x
Database:     Supabase (shared with main app)
Deployment:   Vercel / Cloudflare Pages
Images:       Astro Image (built-in optimization)
Search:       Pagefind (static search, 0 API cost)
RSS:          @astrojs/rss
Sitemap:      @astrojs/sitemap
Analytics:    Plausible / PostHog (privacy-first)
```

---

## 10. Execution Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Set up Astro.js project with Tailwind
- [ ] Connect to Supabase (read-only for news site)
- [ ] Build layouts: base, article, category, wire
- [ ] Implement article page with JSON-LD
- [ ] Google News sitemap + RSS

### Phase 2: Content Pipeline (Week 2-3)
- [ ] Implement `classify_publish_tier()` function
- [ ] Build article generation prompt
- [ ] Create article generation worker (runs after AI summary)
- [ ] Slug generation + deduplication
- [ ] Backfill existing Tier 1 filings (last 30 days)

### Phase 3: Pages & SEO (Week 3-4)
- [ ] Homepage with featured articles + live wire
- [ ] Category pages with pagination
- [ ] Company pages
- [ ] Search (Pagefind)
- [ ] OG image generation
- [ ] Submit to Google News

### Phase 4: Lead Gen & Launch (Week 4-5)
- [ ] CTA components (in-article, bottom bar, sidebar)
- [ ] Email capture form → Supabase
- [ ] A/B test CTAs
- [ ] Analytics setup
- [ ] Launch on `news.marketwire.app`

### Phase 5: Iteration (Ongoing)
- [ ] Daily roundup articles (auto-generated)
- [ ] Sector-level summary pages
- [ ] "Most read" / trending
- [ ] Push notifications via web
- [ ] Expand to more categories as content grows

---

## 11. Admin Panel Extensions

### For the existing admin panel:
- **Publish Tier Dropdown** — Override auto-classification on any filing
- **"Regenerate Article" Button** — Re-run the article generation prompt
- **Stale Article Warning** — When admin edits a filing that has a generated article
- **Article Preview** — See generated article before publishing
- **Bulk Actions** — "Publish all Tier 1 from today", "Regenerate stale articles"

### Article Correction Cascade
```
Admin corrects filing data (headline, summary, category)
   │
   ▼
Set article_stale = true on that filing
   │
   ▼
Background worker picks up stale articles
   │
   ├── If article_manually_edited = true → Skip (preserve manual edits)
   └── If article_manually_edited = false → Regenerate article from updated data
```

---

## 12. Cost Estimates

| Item | Monthly Cost |
|------|-------------|
| Article generation (GPT-4o-mini) | $150-360 |
| Astro hosting (Vercel/CF Pages) | $0-20 |
| Supabase (shared, no additional) | $0 |
| Domain (news.marketwire.app) | $0 (subdomain) |
| **Total** | **$150-380/month** |

---

## Prerequisites Before Building

Before starting the Astro.js news site, complete these backend tasks:

1. **Backfill sector & market cap data** — From tet.json into `stocklistdata`
2. **Fix company management** — Auto-apply ISIN changes, handle cascading updates
3. **New authenticated corporate filings API** — With watchlist, read/unread, market cap filters
4. **Fix cron jobs** — Python-based scheduling for corporate actions, insider trading, deals
5. **Add `market_cap` and `sector` to `stocklistdata`** — Required for tier classification
