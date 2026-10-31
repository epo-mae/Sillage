# Layering: personal evidence before recommendations

Open **Collection → Layering** to save a combination. Choose two distinct bottles,
their application order and spray amounts. Optional notes describe why you want
to try it. Different amounts or order create a different recipe, with separate
evidence. Saved recipes are not automatically recommendations.

**Ideas to test** shows at most three possibilities when both bottles individually
fit the current context, have a shared source accord, different accord profiles,
and a known contrast in freshness or richness. This is a discovery heuristic, not
evidence that scents blend well. With insufficient data, no ideas are generated.
Any two active bottles can still be saved as a personal test.

Use **Log pair wear now** to record an experiment. The app saves both bottles,
order, amounts, local time, weather and context in an immutable snapshot. In
**Journal → Layered wears**, record enjoyment, whether it was better than either
fragrance alone, combined strength, and optional observed longevity and notes.
Feedback is editable. Pair ratings and longevity never train individual bottles'
ratings or longevity. Participation counts toward rotation, collection wear counts,
and the never-worn filter.

## When Today may show a pair

Singles remain the default. No pair fit score is invented or averaged. At most one
optional pair appears, selected by observed personal preference:

- Both bottles are active and score at least 7/10 individually, with no penalties.
  Every known temperature, weather, time, season, occasion, environment, projection
  and longevity component must score at least 6/10.
- The exact recipe has positive reviews on at least three different local dates
  in comparable conditions. Repeated logging on one day cannot satisfy this gate.
- At least 80% of the last ten matching reviews rate it 4/5 or higher, say
  **better together**, and report **just right** strength. Mean enjoyment is at
  least 4/5. The latest reviewed wear must also be positive. New negative feedback
  pauses suggestions until a later positive result, with all gates still enforced.
- Known observed longevity shorter than the current planned duration prevents
  qualification. Unknown longevity is excluded rather than invented.
- If the strongest single is part of the pair, explicit better-than-either-alone
  feedback supplies the comparison. Otherwise, that strongest single needs at
  least three comparable personal reviews and the pair's observed average must
  exceed its average by at least 0.5/5.

These are conservative product rules, not scientific guarantees. High individual
scores or shared notes alone never qualify a pair.

## Weather and time

Known current daypart, occasion and environment must match historical records.
Temperature and feels-like must each be within 5°C; humidity within 20 percentage
points; wind within 12 km/h. Precipitation must match wet versus dry. These
tolerances are explicit heuristics. Unknown current variables are ignored; an
unknown historical value cannot prove similarity to a known current value.

The usual individual temperature limits still apply. Combined strength comes from
feedback on the exact recipe, rather than an average of projection estimates.

## Storage and operations

Schema migration 4 adds `layerings` and `layering_wears` to the existing SQLite
database and Docker volume. Solo history is preserved. Removing recipes archives
them; historical snapshots and feedback remain in the journal and private export.
Removing either bottle makes its recipe unavailable for logging and suggestions.

Suggested-pair logging requires an owned, fresh Wear Now recommendation containing
that pair. One recommendation records either a solo or paired wear, not both;
cross-table checks are serialized. Request identifiers prevent duplicate retries.
Authentication, ownership and CSRF checks remain server-enforced. Exploration
logs are explicitly marked as experiments.

API endpoints:

- `GET /api/layerings`: active recipes and historical paired wears.
- `POST /api/layerings`: save a recipe.
- `DELETE /api/layerings/:id`: archive a recipe.
- `POST /api/layerings/:id/wears`: record an experiment or supported suggestion.
- `POST /api/layering-wears/:id/feedback`: save or edit feedback.
- Recommendations include `layering_option` (or null) and `layering_experiments`.
- `/api/export` includes recipes, paired snapshots and feedback.

Tests cover evidence gates, weather/time changes, recipe-specific learning,
negative feedback, baselines, validation, authentication, retries, migrations and
shared wear slots. `tests/layering-browser.cjs` covers the save/log/feedback/archive
flow against a fresh isolated preview. Never seed its fixtures in a real account.
