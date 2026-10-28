# BookScout USA · Nationwide Sourcing Radar

An independently runnable, static web application plus an hourly GitHub Actions updater. No Work credits, web-app server or paid database required. The local standalone HTML works offline apart from map tiles and optional Open Library metadata lookup.

## What is included

- USA map of documented venue/source locations, with state and city filters, popup source links, and manual city geocoding when internet is available.
- 175 researched source and event records across regional suppliers and national portals (not 175 current purchasable lots).
- 110 nationwide Google News discovery RSS queries: two searches per state and DC (library/friends sales; bulk/institutional/auction) plus eight nationwide niches. Every run checks one query per state and all national queries; the other topic is checked the next hour.
- 49 source-page monitors, checked in a four-hour rotating cycle; page changes and any public schema.org Event metadata are processed separately from unverified news headlines.
- Source health, dates of last successful checks, failures, duplicate suppression, 60-day discovery history, and first-run baseline behavior.
- Notifications: on-page alert inbox, browser notifications when the web app is open, and optional background Discord webhooks. New candidates, official events, official-page changes, and events ending by tomorrow are distinct types. End dates are date-only unless the organizer provides a time.
- Calendar scoped by state, city, source type, with only **dated** records (no invented dates).
- ISBN CSV import/export, manual ISBN validity check, on-demand Open Library edition title lookup, scorecard grouped by actual sale, and separate list of unranked books and sales without a manifest.
- Source-specific private notes, watchlist, local JSON backups, and a bulk-book ROI calculator.

## Live status and honesty

The zip is a **working program, not a hosted live service until deployed**. Open `web/index.html` to preview it. `BookScout_USA_Offline.html` is the single-file portable version, with 175 curated sources. The live public report initially has zero feed results until the first workflow runs.

This is **nationwide monitoring**, not a guarantee of indexing every sale in America. News RSS can miss small institutional sales, auction platforms without open feeds and undigitized local library events. Page change does not establish new inventory, and RSS 'state' is a query target, **not a verified listing address**. The map deliberately refuses to invent coordinates for these leads.

No online Amazon Best Sellers Rank or eBay sold comps are fetched automatically. Open Library only supplies bibliographic metadata; licensed seller APIs or imported trustworthy resale data are needed for rankings. A sale without a manifest is not scored.

## Turn on hourly updates and optional alerts, one-time setup

1. Create a **public** GitHub repo `bookscout-usa`, empty without initializing README or other files. GitHub Pages on Free generally needs a public repo. Do not use your unrelated existing repositories.
2. Unzip the whole download. In a Terminal inside the `BookScout_USA` folder (the one containing `.github`, `scripts`, `config`, `web`), run:

   ```sh
   git init
   git add .
   git commit -m "BookScout USA live tracker"
   git branch -M main
   git remote add origin https://github.com/YOUR_GITHUB_USERNAME/bookscout-usa.git
   git push -u origin main
   ```

   Substitute your actual GitHub username. Or upload the *complete folder contents* through GitHub Desktop, preserving `.github/workflows/bookscout-usa.yml`.
3. In the repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. **Actions → BookScout USA hourly refresh → Run workflow**. Open the run logs and confirm the sources were actually checked. The site's live URL will be `https://YOUR_GITHUB_USERNAME.github.io/bookscout-usa/` after the Pages deploy succeeds.
5. It schedules at `:17` of each hour in UTC, but GitHub may delay or skip a run under load. The web app polls the **published report** every five minutes; that is **not** a new crawl every five minutes. Source health displays technical failures honestly.

### Background notifications when the website is closed

Discord (free): Create a webhook in a private channel. Set GitHub **Settings → Secrets and variables → Actions → Secrets → New repository secret** named `DISCORD_WEBHOOK_URL` with its full URL. Do not paste credentials into the app or public repo. Optionally add repository variable `ALERT_STATES` with comma-separated state codes like `VA,NC,MD,DC` to filter webhook alerts. The website's browser notifications work only while the page is open and permission is enabled.

### Update frequencies

- GitHub scheduled job: hourly, subject to GitHub delays and limits.
- Each state's library-sale topic: about every **2 hours**. Its institutional/bulk topic: on alternating hours. Eight national feeds every hour.
- Each official site monitored: approximately every **4 hours**.
- Browser polls published JSON: every **5 minutes**, while open.
- Source results are never declared fresh just because the workflow ran; last successful time is tracked per source.

## Add trusted data (sources / ranking)

- `config/feeds.json`: actual HTTPS RSS/Atom endpoints. RSS news results are unverified signals.
- `config/watch_pages.json`: public organizer and category pages only, respecting robots.txt. If they expose JSON-LD `Event` metadata, dated opportunities can be extracted. Monitor status tells you if blocked.
- `data-seed.json`: researched or user-confirmed source/event rows with original URLs and evidence flags. Re-run `python scripts/rebuild_seed_js.py` after manually changing this file.
- Rankings: download the CSV template from the rankings tab. Columns: `source_id,isbn,title,amazon_bsr,amazon_price,ebay_sold_price,cost,fees,shipping,checked_at,notes`. Make `source_id` match the existing sale's ID to group and rank its book list. Numeric values without verified evidence are not useful. A price is not proof of a completed sale.

## Test locally

```sh
python3 -m unittest discover -s tests -p 'test_national.py' -v
python3 scripts/national_update.py  # with internet: makes one real public-source pass
python3 -m http.server 8000 --directory web
```

Open `http://localhost:8000/`. Chrome/Edge/Safari support may vary for Notification APIs; HTTPS is preferable for notifications.

### Files

- `web/index.html`, `web/app.js`, `web/app.css`: app and UI
- `web/data/seed-data.js`: researched baseline for standalone browser use
- `web/data/live.json`, `web/data/live-data.js`: last generated update, initially empty
- `scripts/monitor_core.py`, `scripts/national_update.py`: public-source polling, parsing, checking, alerts
- `config/feeds.json`: 110 nationwide queries
- `config/watch_pages.json`: 49 direct public-page watches
- `.github/workflows/bookscout-usa.yml`: hourly scheduler + Pages deployment
- `tests/`: tests for state coverage, alternating fetches, structured events, error recording, deduplication and browser UI

**Privacy:** local notes, ISBNs, saved leads and alert-read markers stay in your browser. They are not uploaded to GitHub. Public repositories expose the **configuration and researched source list**. Export backups before changing origins or clearing browser storage. Webhook secrets must only be stored in GitHub Actions Secrets.
