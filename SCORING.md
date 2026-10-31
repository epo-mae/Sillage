# Understand and adjust the ranking

Open **Preferences → Your priorities**, now the first preferences section.
Each factor has an importance slider from 1–10 and a checkbox to turn it off.
Importance is relative, not a percentage. The sliders do not need to total 100.

- **Balanced**, **Weather first**, and **More variety** are editable presets.
- **Reset defaults** restores the original default weight proportions on the
  editing scale. Presets and resets are previews until saved.
- **Save these priorities** saves only the priorities. **Save preferences** saves
  the whole preferences form, including priorities, location, presence and variety.
- Existing weight settings remain intact until you explicitly save new priorities.
  Legacy ratios are displayed on the 1–10 editing scale, rounded to a tenth.

## Live previews

Move sliders to see the ranked collection change, including up/down movement from
the initial preview. Expand **Why this rank?** to inspect the factors. Desktop keeps
the preview beside the controls; mobile shows a compact current leader while you
scroll the sliders, with the full results below.

Previews use one fixed context and your saved non-priority settings. They never
create recommendation-history entries, wear logs, or saved preference changes.
The context is server-signed and expires after an hour; reopen Preferences to get
a fresh context. Presence and variety-strength edits take effect after saving the
whole form. Network responses from superseded slider requests are discarded.

## Importance, share, fit, and information quality

The score breakdown separates four different concepts:

1. **Importance:** your 1–10 setting, or Off.
2. **Share of score:** the actual percentage allocated to that factor for this
   fragrance. Unknown factors are excluded, and remaining weights are normalized.
   Different fragrances may have different shares because their known data differs.
3. **Fit:** suitability out of 10 for that particular factor. A large importance
   does not imply that the fragrance fits well.
4. **Information quality:** Limited information, Some supporting information, or
   Well supported. This remains separate from fit.

Overall and per-factor fit use the engine's 0–100 values divided by ten. A zero is
labelled **No fit**, and a positive score below one is labelled **Below 1/10**.
Unassessable profiles remain **Not scored**. Source star ratings, personal wear
ratings and factual measurements retain their labelled original units.

**Show calculation** retains exact raw calculations and snapshots for inspection.
Normal explanations convert score points and fit limits to the 10-point scale.

## Limits

Temperature mismatch limits apply while Temperature is enabled. Turning off that
factor disables its model limit. Rotation's overall share never exceeds 4%, even
if its importance is 10 or many other factors are unknown.

**Variety strength** controls how sharply recent wears reduce the rotation factor;
**Variety importance** controls how much that factor matters overall. Preferred
presence is the target; Presence match importance controls how much matching it
matters. These are deliberately separate controls.

Open a fragrance's **Edit → Personal boundaries** to set a minimum or maximum
temperature in Celsius, or exclude it in confined spaces. These personal rules
override scores and cannot be outweighed by sliders. A matching rule excludes the
fragrance from suggestions and explains why. Unknown temperature or environment
does not trigger a rule. If every fragrance is excluded, Today asks you to review
the boundaries rather than recommending an excluded bottle.

Rules are preserved on provider refresh, checked against stale recommendation logs,
and respected by layering recommendations. They are personal preferences, not
universal claims about a fragrance. Historical snapshots are not rewritten.

## Technical notes

- `POST /api/recommendations/preview` accepts an exact `importance` map with every
  factor in the 0–10 range (0 = Off), plus an optional existing recommendation ID
  or a signed preview token. It returns rankings, shares, context and a refreshed
  preview token, with no database writes.
- Saving `preferences.importance` also updates the underlying weights. Legacy
  weight updates remain supported and clear the importance map. Supplying both
  formats in one request is rejected.
- Fragrance `limits` contains optional `min_temperature`, `max_temperature`, and
  boolean `avoid_confined`. Missing or legacy-null limits mean no personal rules.
- Engine version 6 adds actual factor shares, personal exclusions and priority
  snapshots. The database's JSON fields support this without rewriting accounts.
- Tests cover non-saving previews, signed/frozen contexts, validation, ranking
  changes, normalized shares, bounded rotation, unknown factors, boundary overrides,
  stale recommendations and provider-refresh preservation. Browser checks cover
  presets, keyboard sliders, saving, mobile previews and the personal boundary UI.
