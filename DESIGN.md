# Sillage: product and design direction

## Design implemented

The interface uses a charcoal navigation rail, warm paper surfaces, serif titles,
readable system text, and a restrained brown accent. Product images carry the visual
identity. Missing images use an honest typographic placeholder. Rules and spacing
separate information; cards are reserved for the main recommendation and product
selection. Mobile keeps a compact bottom navigation and a two-column collection.

Today answers what to wear, why it fits, and how to record it. Collection is a
visual inventory. Journal records outcomes. Preferences contains configuration.
Language should describe those jobs directly and avoid slogans and ritual copy.
Fit scores are points out of 100, distinct from confidence in the available data.

## Next improvements, in recommended order

1. **Set today's context in place.** Put occasion, indoor/outdoor setting, and
   intended duration beside Wear now / Tonight. Show an editable summary before
   recommending. Keep these temporary choices separate from saved preferences.
   This removes trips into settings and lets the user correct inferred plans.
2. **Log any bottle directly.** Add Log wear to collection details, with date/time
   and optional sprays. Current logging requires a current recommendation; extend
   the backend to support independent wears without inventing a recommendation.
   A journal needs to record what the user actually wore.
3. **Make explanations comparative.** Lead with two or three concrete reasons:
   expected duration, projection fit, and temperature suitability. Explain the
   tradeoff against the runner-up. Keep weighted tables under an advanced disclosure.
   Distinguish missing context from poor fragrance fit.
4. **Reveal collection habits.** Add Unworn recently and Most reached for views,
   plus a simple wear calendar. Use the user's recorded history; avoid unsupported
   claims about taste. Let users choose their own rotation window.
5. **Make feedback easier.** Offer a short follow-up for an unreviewed wear:
   liked it, strength, observed duration. Allow skipping, and make corrections
   easy. Explain how personal observations change future recommendations.
6. **Refine fragrance details.** Present note layers, accords, personal notes,
   and wear history as one readable profile. Keep source, refresh date, inferred
   values, and user overrides accessible under Data sources.
7. **Improve setup.** Guide users through adding three bottles, choosing an
   occasion, and optionally enabling weather. Include previews and clear skip
   actions. Replace coordinate entry with place search only when a suitable
   geocoding provider and its attribution are selected.

## Quality bar

- Check populated, empty, loading, provider failure, missing-image, and long-name states.
- Preserve keyboard navigation, visible focus, native dialogs, and text labels.
- Check 390px and desktop widths; prevent horizontal scrolling.
- Use isolated review data; never seed or change the user's collection for screenshots.
- Keep all provider credentials on the server.

## Scope of this pass

Implemented the shared visual system and clearer copy across all existing screens.
The features above are a proposed roadmap, not implemented functionality.
