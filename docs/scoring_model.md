# Scoring model

Every opportunity gets three separate 0-100 scores, calculated in
`app/services/scoring.py` and never combined into one misleading number.
Missing or uncertain information always reduces (never inflates) the score -
"unknown" is treated as unfavourable, not neutral.

Current `scoring_version`: see `SCORING_VERSION` in `app/config.py`
(`2026.1` at time of writing). This is stored on every `Score` row so past
scores remain interpretable even after the formula changes.

## Opportunity score (0-100)

| Component | Max points | How it's computed today |
|---|---|---|
| Discount to conservative market estimate | 25 | **Always 0** - this pipeline doesn't collect a market valuation yet. Wire up a manual valuation input before this component means anything. |
| Location and demand | 15 | 15 if geocoded with high confidence in a target province (Gauteng in the MVP), 7 if in a target province without a confident geocode, else 0. |
| Rental potential | 10 | **Always 0** - no rental-estimate feed yet. |
| Source reliability | 10 | Scaled directly from the parser's field-extraction confidence (0-1) x 10. |
| Property description clarity | 10 | 10 if both an erf/sectional description *and* an improvements description were extracted, 5 if only one, else 0. |
| Occupation clarity | 10 | **Always 0** - a sheriff notice alone never confirms occupation status. |
| Repair-risk estimate | 10 | 3 points if any improvements/condition text was extracted, else 0 (this is a screening signal only, not a repair estimate). |
| Time available for due diligence | 5 | Scaled from days-until-auction, capped at 5 (roughly 1 point per 6 days). |
| Sale-condition completeness | 5 | 5 if a conditions-of-sale reference was extracted, else 0. |

## Risk score (0-100)

Sum of severity weights across every open risk flag on the opportunity,
capped at 100:

- critical: 25
- high: 15
- medium: 8
- low: 3

See `app/services/risk_engine.py` for the full flag list (occupation
unknown, no inspection, voetstoots/as-is sale, reserve price absent, auction
imminent or already past, incomplete address/erf/case-number, stale source,
low geocode confidence, title/deeds verification outstanding, etc).

## Completeness score (0-100)

A weighted percentage of the fields that matter for a sheriff-sale
opportunity (case number, auction date, venue, address, erf/sectional
description, reserve price, deposit terms, contact details, title deed,
province, improvements text, conditions-of-sale reference). Fields are
weighted 1 or 2 depending on how material they are to due diligence - see
the `weights` dict in `calculate_completeness()`.

## What this pipeline deliberately does not do

Per the brief's own coding standards, this pipeline does not use an LLM as
the only (or even primary) extraction method, and does not silently invent
values for missing fields. If you add a market-valuation or rental-estimate
source later, feed it in as an explicit, human-provided or licensed-feed
input (`has_market_valuation=True, market_discount_pct=...` in
`calculate_opportunity()`) rather than having the model guess.
