# TCJC sample input set for the bid-leveling POC

Inputs reverse-engineered from `data/TCJC_CD_Estimate Summary_251211.xlsm` (the finished leveling workbook for the
Teton County Justice Center). Three bid packages, 14 priced bids, 1 superseded bid, 2 decline notices.

Every bid document is stamped **SYNTHETIC TEST DATA**. The firms are real; the documents are not theirs.

## What is real and what is invented

| From the workbook | Inferred | Synthetic (invented) |
|---|---|---|
| Company names; every line amount, quantity and unit price; base bid, Textura, SDI, sales tax, total package value; alternates; recommended bidder; UNRESPONSIVE marks; predicted safety incidents; scope item wording on the scope sheets; the CM/GC estimate | Which lines are the bidder's price and which are CM/GC plugs, for bidders other than the recommended one (the workbook codes cost categories only for the recommended bidder) | Each bidder's wording and layout; warranties; inclusions and exclusions beyond the workbook's confirm marks; labor rates and mark-ups; bid validity; dates and reference numbers; contacts (placeholders); the awarding policy; prequal status and limits; the clarification log; the split of Rodac into an original quote and a revised bid |

The CM/GC is called "CM/GC" throughout. The policy is not any real contractor's policy.

## Layout

```
gc/                              what the general contractor brings
  project_brief.md               project facts, dates, addendum, alternates
  awarding_policy.docx / .md     award and leveling rules
  subcontractor_prequal.xlsx     status, single-project limit, safety score, SDI
  bid_clarification_log.xlsx     questions sent after bid day and who answered
  <package>/scope_sheet.xlsx     scope items + CM/GC quantities, bid form requirements,
                                 required warranties, confidential CM/GC estimate
bids/<package>/                  what the subcontractors sent
answer_key/                      expected result
  <package>.json                 per bidder: lines, plugs, totals, flags, recommended bidder
  answer_key.xlsx                Summary sheet + one side-by-side tally per package (plugs shaded)
```

## Bids and what each one exercises

### 07.50 Roofing (CM/GC estimate $834,914; recommended: Rodac, $849,845.33)

| File | Format | Bid as written | Tests |
|---|---|---|---|
| `Superior Roofing - TCJC Roofing Proposal.pdf` | PDF proposal | $934,812 | Tax status not stated; "included" item with a value shown for information |
| `Rodac_Roofing_Budget_Quote_110625.pdf` | PDF quote | $566,700 | **Superseded** by Rev 1; must not be leveled |
| `Rodac_TCJC_Roofing_Bid_REV1.xlsx` | Excel, own layout | $597,900 | Quantities in squares; flashing "Included" yet plugged $100,000; bond and transition strips plugged |
| `ELITE_TCJC_0750.docx` | Word letter | $857,000 | $40,000 tax-exempt credit as a negative line; safety score 30.76; better warranty |
| `307imperial_quote_justice_center.pdf` | PDF quote | $852,202 | Tax included, no breakout; warranty below minimum; will not split scopes; 30-day validity |
| `Pinnacle - no bid.docx`, `RE_ TCJC 07.50 Roofing - bid invite.pdf` | Word, PDF email | none | Decline notices; must not appear as $0 bids |

### 09.67 Fluid-Applied Flooring (estimate $213,369; recommended: Advanced Concrete Solutions, $314,339.23)

| File | Format | Bid as written | Tests |
|---|---|---|---|
| `Phaze Concrete - 09.67 Bid Form.xlsx` | Excel bid form | $428,000 | Quantities without unit prices; topping slab missing; short warranty |
| `ACS Proposal 25-318 TCJC Fluid Applied Flooring.pdf` | PDF proposal | $248,337 | "inc" lines; sales tax quoted outside the total; fourth lowest price but lowest responsive |
| `Stewart Specialty - Justice Center flooring.docx` | Word, free text, no table | $91,675.03 | **Arithmetic error** (4,529 SF x $7.50 shown as $33,972.03); missing scope; unresponsive |
| `CentiMark_Proposal_TetonCountyJusticeCenter.pdf` | PDF proposal | $108,967 | Three scope items rolled into one line; unresponsive |
| `Axis quote TCJC.docx` | Word, free text | $56,572 | Wrong quantities and units, missing scope, no terms; not prequalified; unresponsive |
| `Diverzify_TCJC_Div09_Resinous_LumpSum.xlsx` | Excel, own layout | $267,925 | Lump sums only; traffic coating excluded and plugged at another bidder's price; no Textura or SDI applied |

### 32.90 Landscaping and Irrigation (estimate $220,269; recommended: Trail Creek Nursery, $342,640.31)

| File | Format | Bid as written | Tests |
|---|---|---|---|
| `Tree and Landscape Co - 32.90 Bid Form.xlsx` | Excel bid form | $366,791.49 | Unpriced item plugged $15,000; Silva Cell contingency plug $60,000; warranty exclusions |
| `WLM Proposal - Teton County Justice Center Landscape.pdf` | PDF proposal, 2 pages | $546,684.63 | No quantities; "Included above"; extra line of its own; outlier paver price |
| `Trail Creek Nursery bid - TCJC landscape & irrigation.docx` | Word letter with table | $277,000 | Bidder-added lines (freight, mobilization, extra maintenance year); many "included" items |
| `OUTBACK LANDSCAPE - TCJC ESTIMATE.xlsx` | Excel, own layout | $459,361.41 | Splits an item others combine; excludes Textura; warranty below minimum |

## How the totals are built

```
bid as submitted + CM/GC plugs          = BASE BID VALUE
BASE BID VALUE + Textura                = SUBCONTRACT VALUE
SUBCONTRACT VALUE + sales tax + SDI     = TOTAL PACKAGE VALUE
```

Applying `gc/awarding_policy` to these inputs gives the workbook's recommended bidder in all three packages.
In flooring that depends on `gc/bid_clarification_log.xlsx`: the three lowest bidders did not answer and are unresponsive.

## Regenerating

```
uv run --no-project --with reportlab --with python-docx --with openpyxl --with pypdf tools/gen_samples/generate.py
```

The script reads every amount from the workbook by cell and stops with an error if a bid's lines plus plugs do not equal the
workbook's base bid, if the totals do not tie, or if any amount cannot be found again in the generated file. To change a
bid or add one, edit `tools/gen_samples/specs.py`.
