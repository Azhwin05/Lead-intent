# eCommerce Lead Gen System

Fully automated B2B lead generation pipeline that finds eCommerce brands spending on Meta ads with an estimated ROAS below 500%, scores them, writes personalised cold emails, and sends them — all while you sleep.

## What This Does

Every morning at 6 AM the system:
1. Scrapes Meta Ad Library for active ecom advertisers across 14 keywords
2. Enriches each brand with founder/CMO contact data (Apollo.io) and traffic metrics (Similarweb)
3. Scores each brand 1-10 for ROAS underperformance risk using GPT-4o
4. Generates a personalised 3-email cold outreach sequence for HOT leads (score ≥ 7)
5. Saves everything to Airtable
6. Adds HOT leads to an Instantly.ai email campaign
7. Posts a Slack summary + individual alerts for score 9-10 leads

## Architecture

```
Meta Ad Library
      │
      ▼ (Playwright)
 [scrapers/]
  meta_ad_library.py ──── raw leads (brand, ad data)
      │
      ▼
 [enrichment/]
  apollo_enricher.py ──── contact: name, email, title
  similarweb_enricher.py ─ traffic: visits, paid %, bounce
      │
      ▼
 [scoring/]
  roas_scorer.py ──────── score 1-10, tier: HOT/WARM/COLD
      │ (filter score ≥ 7)
      ▼
 [outreach/]
  email_writer.py ─────── 3-email GPT-4o sequence
  instantly_sender.py ──── → Instantly.ai campaign
      │
      ├──► [storage/]
      │     airtable_client.py → Airtable Leads table
      │
      └──► [notifications/]
            slack_notifier.py → daily summary + hot alerts
```

## Prerequisites

| Requirement         | Details                                           |
|---------------------|---------------------------------------------------|
| Python 3.11+        | `python --version`                                |
| OpenAI account      | GPT-4o access required (~$20/mo)                 |
| Apollo.io account   | Free tier: 50 credits/month                      |
| Airtable account    | Free workspace                                    |
| Instantly.ai        | $37/mo plan (sending emails)                      |
| Slack workspace     | Free — needs Incoming Webhooks app               |
| Similarweb          | Optional — heuristics used if not configured     |

## Installation

```bash
# 1. Clone / download the project
cd ecom-lead-gen-system

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright's Chromium browser
playwright install chromium

# 5. Copy env template and fill in credentials
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
```

## Configuration

Open `.env` and fill in every value. Required fields:

```env
OPENAI_API_KEY=sk-...
APOLLO_API_KEY=...
AIRTABLE_API_KEY=pat...
AIRTABLE_BASE_ID=app...
INSTANTLY_API_KEY=...
INSTANTLY_CAMPAIGN_ID=...
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

Optional (tune pipeline behaviour):
```env
MIN_SCORE_THRESHOLD=7          # Lower = more leads, higher = more selective
HOT_LEAD_ALERT_THRESHOLD=9     # Only Slack-alert leads above this
SCHEDULE_HOUR=6                # Hour to run (24h local time)
AGENCY_NAME=Your Agency
AGENCY_SENDER_NAME=Your Name
AGENCY_CASE_STUDY_BRAND=Glow Co
AGENCY_CASE_STUDY_RESULT=620% ROAS in 6 weeks
```

## Airtable Setup

1. Go to [airtable.com](https://airtable.com) → Create a new Base
2. Create a table named exactly `Leads`
3. Add the following fields with the **exact names and types**:

| Field Name        | Type            |
|-------------------|-----------------|
| Brand Name        | Single line text |
| Website           | URL             |
| Ad Platform       | Single select   |
| Days Running      | Number          |
| Num Ads           | Number          |
| Monthly Traffic   | Number          |
| Paid Traffic Pct  | Number          |
| ROAS Risk Score   | Number          |
| Lead Tier         | Single select (HOT, WARM, COLD) |
| Score Breakdown   | Long text       |
| Contact Name      | Single line text |
| Contact Title     | Single line text |
| Contact Email     | Email           |
| Contact LinkedIn  | URL             |
| Email 1 Subject   | Single line text |
| Email 1 Body      | Long text       |
| Email 2 Subject   | Single line text |
| Email 2 Body      | Long text       |
| Email 3 Subject   | Single line text |
| Email 3 Body      | Long text       |
| Outreach Status   | Single select (Pending, Sent, Replied, Booked) |
| Date Added        | Date            |
| Notes             | Long text       |

4. Copy your Base ID from the URL: `airtable.com/appXXXXXXXX/...`
5. Get your API key from [airtable.com/account](https://airtable.com/account)

## Instantly.ai Campaign Setup

1. Log in → Campaigns → New Campaign
2. Configure sending account + warm-up (warm up for 2 weeks before going live)
3. Set campaign to "API managed" mode
4. Copy the Campaign ID from the URL
5. Add it to `.env` as `INSTANTLY_CAMPAIGN_ID`

> Note: The email sequences are added via API — you don't need to set up steps manually in Instantly.

## Running the Pipeline

### Test first (recommended)

```bash
# Dry run — no emails sent, no Airtable writes, max 5 brands
python main.py --dry-run --limit 5
```

Review the console output and `logs/pipeline_YYYY-MM-DD.log`.

### Live run

```bash
python main.py
```

### Common CLI flags

```bash
python main.py --dry-run                    # Safe test mode
python main.py --dry-run --limit 5          # Test with 5 leads
python main.py --min-score 8               # Stricter lead filter
python main.py --keywords "skincare,pets"  # Custom keywords
python main.py --log-level DEBUG           # Verbose output
```

## Scheduling (Daily Automation)

```bash
# Start the scheduler (runs daily at configured SCHEDULE_HOUR)
python scheduler.py

# Run once now, then keep scheduling
python scheduler.py --run-now

# Dry-run schedule
python scheduler.py --dry-run
```

To run as a background service on Windows, use Task Scheduler or NSSM.

## Running Tests

```bash
pip install pytest pytest-asyncio pytest-mock responses freezegun
pytest tests/ -v
pytest tests/ -v --tb=short    # Compact failure output
pytest tests/ -k "scoring"     # Run only scoring tests
```

## Troubleshooting

| Error | Fix |
|-------|-----|
| `playwright install` error | Run as Administrator; try `playwright install chromium --with-deps` |
| Meta Ad Library blocked / CAPTCHA | Set `PLAYWRIGHT_HEADLESS=false` in `.env` to watch the browser |
| Apollo returns no contacts | Try different titles; domain may not be in Apollo's database |
| Airtable field mismatch error | Check field names match *exactly* (case-sensitive) |
| OpenAI rate limit | Reduce `MAX_LEADS_PER_RUN` or add `time.sleep()` between calls |
| Instantly 401 error | Regenerate API key in Instantly dashboard, update `.env` |
| Slack not posting | Test webhook: `curl -X POST -d '{"text":"test"}' YOUR_WEBHOOK_URL` |
| Emails going to spam | Warm up your sending domain for 14 days before live sending |
| Pipeline crashes mid-run | Check `logs/pipeline_YYYY-MM-DD.log` — each step logs its own error |

## Project Structure

```
ecom-lead-gen-system/
├── main.py                      # Pipeline orchestrator
├── scheduler.py                 # Daily APScheduler runner
├── .env.example                 # Environment variable template
├── requirements.txt             # Pinned dependencies
├── README.md
├── config/
│   └── settings.py              # Pydantic-settings config loader
├── models/
│   └── lead.py                  # Pydantic v2 Lead model + sub-models
├── utils/
│   ├── logging_setup.py         # Rich console + rotating file logging
│   ├── retry.py                 # Tenacity retry decorators
│   └── rate_limiter.py          # Token-bucket rate limiter
├── scrapers/
│   └── meta_ad_library.py       # Async Playwright Meta Ad Library scraper
├── enrichment/
│   ├── apollo_enricher.py       # Apollo.io contact enrichment
│   └── similarweb_enricher.py   # Similarweb traffic enrichment + heuristics
├── scoring/
│   └── roas_scorer.py           # 5-signal ROAS risk scorer (GPT-4o)
├── outreach/
│   ├── email_writer.py          # GPT-4o 3-email sequence generator
│   └── instantly_sender.py      # Instantly.ai API sender
├── storage/
│   └── airtable_client.py       # Airtable upsert client
├── notifications/
│   └── slack_notifier.py        # Slack Block Kit alerts
├── tests/
│   ├── conftest.py              # Shared fixtures (offline mocks)
│   └── test_pipeline.py         # Full test suite
├── logs/                        # Auto-created; rotating log files
└── data/                        # Auto-created; raw scrape output + usage tracking
```

## After the Build: Week-by-Week Guide

**Week 1 — Build & Test**
- Run all tests: `pytest tests/ -v`
- Test with dry-run: `python main.py --dry-run --limit 5`
- Verify Airtable receives records
- Check Slack alerts post correctly
- Review GPT email quality manually

**Week 2 — Validate Lead Quality**
- Let system run live for 5 days
- Review HOT leads — are they real ecom brands spending on ads?
- Adjust `MIN_SCORE_THRESHOLD` if too many false positives
- Update `AGENCY_CASE_STUDY_BRAND` + `AGENCY_CASE_STUDY_RESULT` with a real result

**Week 3 — Sell the Service**
- Screenshot Airtable with real leads + scores as social proof
- Share reply rate from Instantly dashboard
- Price at $200/booked call or $800–1,500/mo retainer

---

Built with Python 3.11 · Playwright · OpenAI GPT-4o · Apollo.io · Similarweb · Airtable · Instantly.ai · Slack · APScheduler
