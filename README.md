# Sillage

Single-owner access: create the owner account on first launch. Registration closes
after setup, and subsequent visitors can only sign in. Create your account before
sharing the public address.

## Run with Docker

```sh
git clone git@github.com:epo-mae/Sillage.git && cd Sillage && docker compose up -d --build --wait
```

Open `http://127.0.0.1:18473`. Requires Docker Compose and GitHub repository
access. See [DOCKER.md](DOCKER.md) for Fragella configuration, HTTPS, updates,
backups, and moving your existing collection. Private credentials and local data
are excluded from Git and the Docker image.

A personal fragrance intelligence MVP. Sillage evaluates your own collection against local time, forecast conditions, imported plans, projection preferences, wear history and feedback. The premium responsive interface keeps the recommendation first and the analytics secondary.

## Start on Windows

Python 3.11+ is required (tested on 3.14). From this folder:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe run.py
```

If your Python distribution omits pip in virtual environments:

```powershell
python -m pip --python .venv\Scripts\python.exe install -r requirements-lock.txt --index-url https://pypi.org/simple
```

Open http://127.0.0.1:8000 and create an account. Add your actual fragrances using search → select → Add to Collection. Configure `FRAGELLA_API_KEY` in `.env` for the full Fragella catalog. In Preferences, set coordinates and an IANA timezone (for example `Pacific/Auckland`), or grant browser geolocation and save. Weather is requested only after coordinates are saved and weather is enabled. Import an optional `.ics` export for calendar context.

The default collection is empty. Fragrance metadata is imported from a configured provider and cached locally. Without a configured provider, a clearly labeled ten-record FragDB evaluation catalog is available. Manual entry is a secondary fallback. Provider facts, community aggregates, inferred numeric attributes and user overrides have separate provenance. Images use provider URLs, with fallbacks. See [CATALOG.md](CATALOG.md) for configuration, provider terms, data normalization and refresh behavior.

## What's working

- Local registration/login/logout, scrypt password hashes, signed HttpOnly sessions, CSRF validation, per-process authentication throttling, account-scoped data, safe HTML escaping and security headers.
- Search-first fragrance addition with fuzzy autocomplete, sourced notes/accords/performance, release/concentration distinction, duplicate protection and optional personal details. Persistent collection with search, family/favorite/never-worn filters, sorting, editing, favorites and archive.
- Open-Meteo current and seven-day hourly forecast, server-side 15-minute caching, hemisphere-aware season and local timezone.
- Optional private calendar-file import, replacing previous imports atomically. Times and event titles inform a deterministic classification and dynamic 4–12 hour wear horizon. Calendar and weather can be independently disabled; imported events can be deleted.
- Wear Now, Tonight, and selected Event recommendations. Every candidate has a stored score breakdown, normalized weighted contributions, major penalties and a separate reliability confidence. Up to three alternatives appear when enough fragrances exist.
- Context explanations from score data, current collection comparison, Why Not, debug snapshots and historical recommendation inspection.
- Wear records, low-friction feedback, gradual satisfaction/observed-longevity learning, bounded rotation and basic spray adjustment after three strength observations.
- Journal, settings, data export, empty/loading/error/permission-denied states and responsive dialogs with native focus management.

## Architecture & schema

`sillage/app.py` defines authentication, validation and account-scoped internal APIs. `context.py` constructs context and wear horizons; `providers.py` isolates weather and calendar adapters; `catalog.py` defines fragrance providers and normalized metadata; `engine.py` is pure deterministic scoring with no Flask/UI dependencies. `static/` contains the interface. Waitress serves the application.

`sillage/schema.sql` contains idempotent V1/V2 migrations and schema-version markers. V2 adds selected-metadata caching and collection identity indexes to existing databases. The SQLite database uses foreign keys and WAL mode. Relationships:

```text
users → fragrances (owned collection + structured attributes)
users → events (private imported calendar context)
users → recommendations (immutable full context/candidate/metadata snapshots)
users → wears → fragrances + recommendations
wears.feedback → personal performance computed from observations
users.preferences → profile, integration toggles, scoring weights
```

Attributes, preferences and contextual snapshots use validated JSON documents inside relational ownership records. Fragrance archives retain historical references. Recommendation snapshots include engine version and the exact metadata, components, weights and contributions used; later edits do not alter history. For future schema changes, add ordered migrations against `schema_version` rather than modifying deployed tables implicitly.

### Scoring

Default weights: temperature 15, weather 12, occasion 15, environment 10, time 8, season 5, projection 8, longevity 8, preference 10, history 5, rotation 4. Unknown attribute-dependent dimensions are omitted and known weights renormalized. Preference/history start with documented neutral priors. Rotation remains at most four points even when metadata is sparse. Extreme heat with a rich/sweet profile and strong projection in confined settings receive 30-point penalties; severe longevity mismatch or very casual/formal mismatch receive 20-point penalties. Final score is clamped to 0–100.

Confidence is distinct from match: metadata coverage, forecast availability, certainty of plans, community vote support, inferred fields and feedback quantity determine High/Medium/Low reliability. Personal longevity and satisfaction blend with 5–25 equivalent prior observations so a single wear cannot dominate. Community season/occasion/day-night distributions feed the engine directly where supplied, while explicit user overrides take priority. Explanations use actual components and penalties; no LLM chooses the winner.

### Internal API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/session` | Account, CSRF token and defaults |
| `POST /api/auth/register`, `/login`, `/logout` | Account lifecycle |
| `PATCH /api/profile` | Validated preferences |
| `GET/POST /api/collection` | List/add owned fragrances |
| `GET /api/catalog/status`, `/search`, `/fragrances/:id` | Search and inspect normalized catalog records |
| `POST /api/collection/from-catalog` | One-click sourced addition |
| `POST /api/collection/:id/refresh-metadata` | Refresh source data, preserving user overrides |
| `PATCH/DELETE /api/collection/:id` | Update/archive owned fragrance |
| `GET/DELETE /api/events` | Inspect/delete imported calendar |
| `POST /api/events/import` | Import `.ics` text |
| `POST /api/recommendations` | Compute + persist now/tonight/event result |
| `POST /api/wears` | Record a candidate from a recent current recommendation |
| `POST /api/wears/:id/feedback` | Save/edit reflection |
| `GET /api/history` | Wear records + latest 100 recommendation snapshots |
| `GET /api/export` | Download private account data |

Mutating requests require `X-CSRF-Token` from `/api/session` and the same session cookie. Every data query is scoped to the authenticated account. Imported calendar content has a 1 MB request limit and 1,000-event cap.

## Configuration & integrations

`.env.example` documents settings. The ignored project `.env` file is loaded at startup, with process environment variables taking precedence. Restart the server after changing settings. For PowerShell, `$env:SILLAGE_SECRET_KEY = 'your-long-random-secret'` is also supported.

| Variable | Default / purpose |
| --- | --- |
| `SILLAGE_SECRET_KEY` | Auto-generated in ignored `data/session.key`; use a persistent random secret in deployment |
| `SILLAGE_HOST` | `127.0.0.1`; bind externally only behind a configured HTTPS proxy |
| `SILLAGE_PORT` | `8000` |
| `SILLAGE_DATABASE` | `data/sillage.db`; alternate path for isolated test/server instances |
| `SILLAGE_SECURE_COOKIE` | `0` locally; set `1` behind HTTPS |
| `OPEN_METEO_API_KEY` | Optional paid commercial weather key; switches to `customer-api.open-meteo.com` |
| `FRAGELLA_API_KEY` | Private server-side fragrance API credential; automatically selects Fragella |
| `SILLAGE_FRAGRANCE_PROVIDER` | `fragella`, `fragdb`, or `sample` |
| `SILLAGE_FRAGDB_PATH` | Directory of a licensed local FragDB v5 export |
| `SILLAGE_METADATA_TTL_DAYS` | `7`; selected remote detail-cache freshness |

Open-Meteo supports evaluation/non-commercial requests without a key. Commercial deployment needs an appropriate subscription. Attribution is included in the interface. See [API documentation](https://open-meteo.com/en/docs), [terms](https://open-meteo.com/en/terms), and [pricing](https://open-meteo.com/en/pricing).

Calendar import needs no credential. It is a real one-off import, **not OAuth synchronization**. VEVENT times, titles and locations are retained privately; descriptions are not imported. Event type/environment are title-based estimates. Export recurring calendars as expanded occurrences: RRULE inputs are explicitly rejected. For Google/Microsoft OAuth in phase 2, register a provider application and configure client ID, client secret, redirect URI, minimal read-only scopes and encrypted token storage. These OAuth endpoints are not implemented in V1. No AI service is configured; adding AI interpretation later requires a server-side API key and sending only minimized context.

## Verification

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check static\app.js
```

Engine tests cover heat, cold, humidity, office confinement, date nights, weddings, outdoors, long plans, no weather/calendar, sparse metadata, rotation, favorites, gradual personal performance, hemisphere season and forecast horizon. API tests cover the complete registration → collection → recommendation → wear → feedback → edit → restart path, account isolation, CSRF, invalid metadata, archival and immutable history.

Optional browser verification uses a locally installed Playwright package and Microsoft Edge. Install `playwright` as a development tool or set `SILLAGE_PLAYWRIGHT` to your existing package path, then run `node tests/browser.cjs`. It starts a separate server/database on port 8001, runs desktop/mobile interactions and writes screenshots to `artifacts/`. Use `SILLAGE_BROWSER=chrome` to select Chrome instead. Browser test data lives separately in ignored `data/browser-test.db`.

## Deployment limits and next phase

This is a functional single-host MVP, not a completed hosted service. Before public deployment, configure HTTPS, a strong stable session secret, secure cookies, backups, operator monitoring and an appropriate weather license. SQLite suits one host; multiple replicas need PostgreSQL and shared rate limiting. There is no email verification/password recovery service or calendar OAuth synchronization. Back up the database using SQLite's backup API rather than copying an active WAL database alone. Account data is not encrypted at rest; use encrypted disks and restrict access to `data/`. Do not commit databases or session secrets.

V1 uses a four-hour horizon without plans and extends to relevant event ends up to 12 hours. It does not infer travel time or forecast destination weather. Event planning outside the seven-day forecast gracefully omits weather. AI semantic classification, destination forecasting, advanced feedback similarity, selectable 2–4 comparisons, Surprise Me, future custom date/location planning, push notifications and native apps are future work. Fragrance search/provider integration is implemented; source data and user overrides are cached without silent overwrites. Fragrantica reference links are supported where supplied by a provider; direct ingestion requires an authorized API agreement.
