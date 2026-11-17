# Evaluation against the sample answer keys

Run on 2026-11-17 with `gemini-4-hydrogen`, using `app/backend/eval/run_eval.py`. The last full run covered all ten packages;
every one recommends the bidder its answer key expects. The real pipeline was run
on every sample bid; nothing was hand-corrected. Re-run with:

```
cd app/backend
uv run python eval/run_eval.py scenario
uv run python eval/run_eval.py workbook
uv run python eval/run_eval.py twenty
```

## Scenario set (`samples/tcjc_plugging`, 12 bids, fictional bidders)

Compared cell by cell with the answer keys computed by the reference engine.

| | Roofing | Flooring | Landscaping | All |
|---|---|---|---|---|
| Bidders identified | 4 of 4 | 4 of 4 | 4 of 4 | 12 of 12 |
| Cell status (priced / included / gap) | 24 of 24 | 36 of 36 | 64 of 64 | 124 of 124 |
| Amount as bid | 16 of 16 | 26 of 26 | 55 of 55 | 97 of 97 |
| Quantity and unit as bid | 7 of 7 | 23 of 23 | 41 of 41 | 71 of 71 |
| Leveled value after unit and quantity normalization | 16 of 16 | 26 of 26 | 55 of 55 | 97 of 97 |
| Plug value equals the answer key | 6 of 7 | 4 of 6 | 5 of 7 | 15 of 20 |
| Lowest leveled total is the same bidder as the key | yes | yes | yes | |

The five plug differences are all items whose policy method is the AI estimate. The answer keys were
computed before the model was connected, so they hold the fallback value; the app now uses the live AI
estimate. Example: ballasted TPO roof, AI estimate $58,305 ($34.50/SF with web sources) against the key's
fallback of $39,442 (average of bidders). These are differences in method, not reading errors.

Unit conversions exercised and correct: roofing squares, square metres, square yards, cubic yards at a
depth, mulch at a non-specified depth, sod rolls, fence panels.

## Workbook set (`samples/tcjc`, 15 bid documents, real workbook figures)

The baseline items were read by the model from each scope sheet (5, 10 and 25 items).

| | Roofing | Flooring | Landscaping |
|---|---|---|---|
| Bid total as written, read correctly | 5 of 5 | 6 of 6 | 4 of 4 |
| Decline notices recognised | 2 of 2 | none | none |
| Superseded quote recognised | 1 of 1 | none | none |
| Recommended subcontractor | Rodac | Advanced Concrete Solutions | Trail Creek Nursery |
| Recommended in the TCJC workbook | Rodac | Advanced Concrete Solutions | Trail Creek Nursery |

In flooring, the three lowest-priced bidders were disqualified by the pass/fail rules the model derived from
the policy (no answer to clarification questions, addenda not acknowledged), which is the same outcome as
the workbook's UNRESPONSIVE marks. Leveled totals are not compared for this set: the workbook's plugs were
estimator judgement, not a rule.

## 20-bidder set (`samples/tcjc_20`, 66 documents, complete scope)

Three packages built on their complete workbook scope (23, 20 and 20 items), 20 fictional bidders each, plus a
superseded quote and a decline notice per package. Compared cell by cell with the answer keys.

| | Landscaping 32.90 | Site Utilities 33.00 | Concrete Paving 32.13 |
|---|---|---|---|
| Bidders identified, declines and superseded quotes recognised | 20, 1, 1 | 20, 1, 1 | 20, 1, 1 |
| Bid totals | 20 of 20 | 20 of 20 | 20 of 20 |
| Cell status (priced / included / plugged) | 460 of 460 | 400 of 400 | 400 of 400 |
| Amounts as bid | 437 of 437 | 376 of 376 | 380 of 380 |
| Quantities and units as bid | 347 of 347 | 191 of 191 | 97 of 97 |
| Unit conversions | 23 of 23 | 23 of 23 | 20 of 20 |
| ... of which only the bid text explains the unit | 5 of 5 (tons of cobble) | 4 of 4 (20 ft pipe joints) | none |
| Quantity re-extensions, leveled values, plug values | all correct | all correct | all correct |
| Qualification agrees with the policy | 20 of 20 | 20 of 20 | 20 of 20 |
| Recommended bidder as the answer key expects | yes | yes | yes |

Two fixes came out of this set:

- **Reconciling bid lines with the stated total.** One bid listed a "Winter protection allowance" that is part of its total;
  the model filed it as an allowance outside the total. The app now counts such lines when, and only when, that makes the
  lines add up exactly to the total the bid states.
- **The award rule.** The app had recommended the highest weighted score among qualified bidders. The policy says to award
  to the lowest responsive, responsible bidder, with a best-value exception only within 3%. In Site Utilities this picked a
  bidder 3.18% above the lowest. The model now also reads the award rule from the policy (basis and best-value window); it
  is shown and editable on the Policy page.

The first run also caught a fault in the generated documents, not the app: one layout omitted the addendum
acknowledgement, and the app correctly failed those bidders. The layout was fixed and the answer key re-checked.

A first leveling of a 20-bidder package takes about 9 to 10 minutes and roughly 85 model calls.

## Ordinals generated from the award policy

1. Leveled Total Package Value, 60%
2. Scope Completeness, 12%
3. Safety Record and Risk, 10%
4. Warranty Compliance, 8%
5. Schedule and Bid Validity, 5%
6. Staffing and Bid Responsiveness, 5%

Plus nine pass/fail rules read from the policy (timely bid and addenda, clarification response, 60-day
validity, prequalification status, single-project limit, safety approval, low-bid scope review, warranty
shortfall, all-or-nothing bids).

## Speed and cost

A first leveling of a package with 4 to 6 bids takes 2 to 4 minutes and 18 to 37 model calls (one per proposal, one
per bidder to assess, one per bidder to explain, one per scope item). Re-leveling after an override takes
under two seconds because unchanged calls come from the cache. The 50-bidder, 40-item generated package
levels in about a second with templated text (AI text is switched off for it by default; switching it on
would add about 140 calls).

## What was not verified

- The app was checked from screenshots of every screen and through the API (upload, AI scope reading,
  leveling, overrides, reset, export). Mouse interaction in a browser (hover tooltips, the cell menu,
  drag-and-drop upload, slider editing on the Policy page) was not exercised by hand. A package with a
  single bidder was not opened in the app; the engine handles it in the tests.
- Judgement rules often come back "unknown" when the supporting documents do not cover a bidder; unknown
  is treated as a pass with a note. A real deployment needs the prequalification and clarification data
  as structured inputs.
- Pass/fail judgements are the model's reading of the documents and were not independently checked.
- Flag rate (the orange dot) is 3% to 17% of cells in most packages and 31% in the workbook landscaping
  package, where many bids quote mulch by the cubic yard with no depth and cannot be converted.
- Extraction accuracy was measured on these 27 generated documents only. They include different layouts,
  units and wording, but no scanned or handwritten bids.
