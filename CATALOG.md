# Fragrance search & metadata

Add Fragrance opens a debounced search with keyboard autocomplete. Select the
correct release and concentration, inspect its source metadata, and click **Add
to Collection**. There is no required metadata form. The saved confirmation offers
**Done** or optional personal rating, bottle size, favorite, notes and longevity on
your skin. Manual creation appears only under **Can’t find it? Add manually**;
brand and name are enough and other fields are collapsed.

## Configure Fragella

Create or edit the ignored `.env` file in the project root:

```dotenv
FRAGELLA_API_KEY=your_private_api_key
SILLAGE_FRAGRANCE_PROVIDER=fragella
```

Restart Sillage. An API key automatically selects Fragella even if the second
setting is omitted. Use the private server API key, not a `pub_` widget key. The
key is read only on the server and is never sent to the browser. `.env` is loaded
at startup; process environment settings take precedence. For a safe credential
check, run `.venv\Scripts\python.exe scripts\check_fragella.py`. It prints only
status and non-secret diagnostics, never the key or raw response bodies.

Provider requests use documented `GET /api/v1/fragrances?search=…&limit=10` and
`GET /api/v1/fragrances/:id` endpoints with `x-api-key`. Honest application
identification uses `User-Agent: Sillage/0.2`. Search inputs tolerate capitalization,
partial matches and minor typos through the provider's fuzzy search; common
abbreviations such as YSL, BDC and DHI are expanded locally.

## Other catalogs

- `SILLAGE_FRAGRANCE_PROVIDER=fragdb` and `SILLAGE_FRAGDB_PATH=C:/path/to/export`
  select a licensed local FragDB v5 directory. Required: `fragrances.csv`;
  reference files: `notes.csv` and `accords.csv`. Files are pipe-delimited UTF-8.
  Missing reference entries stay missing. File changes are detected on lookup.
- `SILLAGE_FRAGRANCE_PROVIDER=sample` selects the included ten-record FragDB
  evaluation sample, with visible attribution and a catalog-size warning. It is
  not a full catalog and does not include Sauvage Elixir or Dior Homme. This
  sample is non-commercial only; use a licensed provider for production.
- `FragranceDataProvider` in `sillage/catalog.py` defines search, record, notes,
  accords, ratings, season/occasion and performance methods. A future first-party
  or authorized provider can implement that contract. UI/scoring never consume
  provider-specific response objects.

## Normalized schema & provenance

Each `FragranceMetadata` snapshot includes schema version, provider name, external
ID, retrieval timestamp, canonical identity, brand, name, release year, optional
release/reformulation version, concentration, gender classification, HTTPS bottle
URL, optional source link, note pyramid, accord strengths, community rating,
performance descriptors/estimates, normalized community aggregates and provenance.

Community aggregates retain `values`, original scores where applicable, `counts`,
`sample_count`, normalization method and source. Multi-select season vote totals
are not claimed to be distinct respondent counts. Fragella returns relative
season/occasion scores and a Bayesian rating but **does not currently expose raw
rating/vote counts or day/night distributions in its documented/live response**.
Those remain unavailable. Ranked scores normalize relative to their maximum and
are labeled as provider suitability, not community vote percentages. Descriptive
value perception is retained as a descriptor, never converted to invented votes.

Numeric scent attributes derive conservatively from source accords. Categorical
longevity/projection are converted to versioned midpoint/weighted estimates.
These fields have `source=inferred`; provider facts and community aggregates stay
separate. No LLM request is needed. Missing concentration, years or note references
are never guessed. Derived accord strengths are shown with ≈ when applicable.

Explicit edits are tracked by field path in `overrides` and marked `source=user`.
Refresh rebuilds the source prior, then overlays every user override, including
cleared attributes. Personal rating, notes, bottle size, favorite and skin
longevity are retained. Unchanged number-input strings do not accidentally become
overrides. The complete original metadata is retained for inspection.

## Local persistence & refresh

The idempotent V2 schema adds `catalog_metadata` and active-collection uniqueness
indexes to existing databases. Search responses are held in a bounded 100-query,
15-minute in-memory cache. Only selected profiles are persisted. A complete
Fragella search response can populate selection immediately without an additional
detail request; otherwise the ID endpoint supplies it. Unowned persisted detail
previews expire after one day. Owned metadata is copied into the collection so
recommendations and historical snapshots work without any catalog request.

Remote detail-cache freshness defaults to seven days (`SILLAGE_METADATA_TTL_DAYS`).
The fragrance detail view shows the retrieval date, a stale indicator and **Refresh
community data**. This refresh re-fetches only that fragrance and preserves user
edits. No bulk harvesting or automatic repeated API calls are performed.

Duplicate prevention uses stable provider IDs and, when year and concentration
are known, a normalized brand/name/year/concentration/release identity. Thus
duplicate upstream slugs for the same bottle do not bypass protection, while EDT,
EDP, Parfum, Elixir, different years and explicitly supplied reformulations remain
distinct. Unknown versions use provider IDs rather than guessing equality.
Database indexes protect concurrent additions. Archived versions can be re-added.

## Recommendation integration

The deterministic engine consumes normalized community season, occasion and
day/night suitability as priors. Context, hard penalties and user overrides take
priority. Ratings shrink toward neutral when counts are sparse. Personal
longevity and satisfaction blend gradually with 5–25 equivalent prior
observations, based on available community evidence; one or two wears cannot
erase a strong prior. Confidence reflects vote support and inferred fields, so
five votes carry less reliability than ten thousand. Counts absent from the API
remain unknown. User-entered skin longevity is an explicit personal override.

## Provider terms reviewed on 2026-10-06

- [Fragella API docs](https://api.fragella.com/docs.html) document the authenticated
  endpoints and payload. [Terms](https://api.fragella.com/terms-of-use.html) allow
  application integration under a subscription and prohibit standalone data
  resale and caching large portions to avoid fresh API access. This implementation
  stores selected collection profiles, not a mirrored catalog. Confirm your plan
  permits your production retention and volume; no subscription was purchased.
- [FragDB sample license](https://github.com/FragDB/fragrance-database/blob/main/LICENSE.md)
  grants CC BY-NC 4.0 use of its sample, with attribution and changes identified.
  The full dataset has separate paid terms. The original license and attribution
  are in `third_party/fragdb_sample/`. A dataset license is not a guarantee of
  independent rights to every third-party image or content item; confirm upstream
  rights for production. Images remain provider URLs, not downloaded assets.
- [Fragrantica terms §5.3](https://www.fragrantica.com/terms-of-service.phtml)
  require written authorization for automation and internal endpoint reuse.
  This app does not scrape Fragrantica or use its private search endpoints. Where
  a provider supplies a corresponding page URL, users can open it as a reference.
  Direct Fragrantica ingestion requires authorized API documentation/permission;
  none was supplied. An adapter can be added once that authorized interface exists.

## Verification

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
node tests\catalog-browser.cjs
node tests\browser.cjs
# Optional — uses configured private API key and a few live requests:
node tests\live-catalog-browser.cjs
```

Browser scripts require Playwright (or `SILLAGE_PLAYWRIGHT` pointing to its local
package) and Edge. Tests use separate accounts, servers and databases; they do not
modify the user's actual collection. Screenshots are saved in `artifacts/`.
