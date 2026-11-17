# TCJC: 20 subcontractors per package (complete scope)

Third sample set for the bid-leveling POC. Each package uses its **complete scope** from the TCJC leveling workbook: every line on the tab that the GC estimated or that two or more real bidders priced. Twenty fictional subcontractors bid each package, plus one decline notice and one superseded quote.

> SYNTHETIC. Scope items and starting prices come from the workbook; bidders, pricing patterns, documents and qualification facts are invented. Every bid document is stamped SYNTHETIC TEST DATA.

## Packages

| Package | Scope items | Proposals | GC estimate | Expected qualified | Lowest leveled (any) | Lowest leveled qualified |
|---|---|---|---|---|---|---|
| 32.90 Landscaping and Irrigation | 23 | 20 + 1 superseded + 1 decline | $381,182 | 15 of 20 | Bradley Lake Landscape Co. | Spread Creek Outdoor Works |
| 33.00 Site Utilities | 20 | 20 + 1 superseded + 1 decline | $1,133,982 | 15 of 20 | Spring Gulch Earthworks | Buffalo Valley Excavation |
| 32.13 Rigid Paving (Concrete Paving) | 20 | 20 + 1 superseded + 1 decline | $889,912 | 15 of 20 | Bivouac Peak Paving | Red Hills Concrete Constructors |

## What the documents exercise

- **Formats and layouts:** PDF proposals and quotes, Word letters and plain-text quotes, Excel bid forms and the bidder's own estimate sheets.
- **Pricing patterns:** complete bids, low bids with scope gaps, high bids, bids that leave out a whole section, items folded into other lines ("included in ..."), a lump-sum-only bid, erratic item pricing, and a revised bid that supersedes an earlier quote.
- **Unit normalization:** square yards, metres, cubic metres, cubic yards at a stated depth, square feet at a different depth, and two units that only the bid text explains (tons of cobble with a stated coverage; storm pipe priced per 20 ft joint).
- **Quantity normalization:** about a fifth of quantity lines differ from the GC takeoff by 6 to 18%; the rest are within 3%.
- **Other lines:** bidder-added items (mobilization, bonds, freight), tax credits shown as negative lines, alternates priced outside the total, and one arithmetic slip per package (a line amount that is not quantity x unit price; the bid is carried as written).
- **Qualification:** in each package five bidders fail a disqualifying rule of the award policy, spread across the price range; the lowest leveled bid is one of them. The facts are in `gc/subcontractor_prequal.xlsx`, `gc/bid_clarification_log.xlsx` and the bids themselves (Addendum 01 not acknowledged).

## Files

```
gc/
  awarding_policy.md / .docx      award rules (lowest responsive, responsible bidder; prequalification; safety; addenda)
  plugging_policy.yaml            default plug method: average of the other bids, then the GC estimate
  subcontractor_prequal.xlsx      status, limit, safety score
  bid_clarification_log.xlsx      questions and who answered
  project_brief.md
  <package>/scope_sheet.xlsx      complete scope with GC quantities; GC estimate tab
bids/<package>/                   20 proposals + 1 superseded quote + 1 decline
answer_key/
  <package>.json                  true reading of every line, leveled values, plugs, totals, qualification, expected award
  answer_key.xlsx                 summary and a tally per package
```

## Regenerating

```
uv run --no-project --with reportlab --with python-docx --with openpyxl --with pypdf --with pyyaml tools/gen_samples/twenty.py
```
