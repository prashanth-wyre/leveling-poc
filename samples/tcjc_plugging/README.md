# TCJC plugging scenario set

A second, designed input set for the bid-leveling POC. It exercises a **plugging policy**, **quantity variance** (a bidder assumed more or less material than the GC) and **unit conversion** (bid unit differs from the GC unit).

> SYNTHETIC. GC scope items and quantities are from the TCJC workbook; bidders are fictional and their prices are designed (mostly real workbook unit rates re-quoted at altered quantities and units; some rates are invented to create specific cases). Totals here do not tie to the TCJC workbook; `samples/tcjc/` is the set that does.

## Inputs

- `gc/plugging_policy.yaml` (+ `.md`): plug methods, per-item rules with fallback chains, comparable pool, quantity normalization, AI method.
- `gc/unit_conversions.yaml`: SQ, SY, m2, CY at depth, rolls, panels.
- `gc/<package>/scope_sheet.xlsx`: scope items with GC quantity and unit, the plug rule per item, confidential GC estimate.
- `gc/awarding_policy.md/.docx`, `gc/project_brief.md`, `gc/subcontractor_prequal.xlsx`.
- `bids/<package>/`: 4 bids per package (PDF, Word, Excel).

## Expected results (`answer_key/`)

`<package>.json` gives, per bidder and line: as bid, converted quantity, variance, action, leveled value; then each plug with method requested, methods tried, pool, trimmed outliers, formula and value; totals; and the award under each plug method. `answer_key.xlsx` shows the same as Summary, Lines, Plugs and Sensitivity sheets.

AI plugs: PENDING: 4 item(s) have no snapshot and no credentials are set; fallback methods used.

## 07.50 Roofing

| Bidder | File | As bid | Qty adjustments | Plugs + allowances | Total package value |
|---|---|---|---|---|---|
| Summit Ridge Roofing | `Summit Ridge Roofing - Proposal 07.50.pdf` | $910,249.20 | $+44,567.51 | $133,650.00 | $1,106,684.35 |
| Highline Roofing & Sheet Metal **(recommended)** | `Highline_Roofing_Bid_TCJC.xlsx` | $596,622.35 | $+0.00 | $225,000.00 | $835,373.82 |
| Cascade Membrane Systems | `Cascade Membrane - TCJC roofing.docx` | $1,004,724.40 | $-46,939.86 | $58,650.00 | $1,033,446.58 |
| Tetonview Roofing | `Tetonview quote - justice center roof (metric).pdf` | $848,733.88 | $+0.00 | $110,381.79 | $975,168.36 |

What each bid tests:

- **Summit Ridge Roofing**
  - RA1: quantity -5.9% vs GC takeoff after converting SF - re-extended, +44,567.51
  - ELD: lump sum with no quantity - cannot check against GC takeoff
  - FLUTE: excluded by bidder - plugged $8,650.00 by average_of_bidders
  - TRANS: excluded by bidder - plugged $75,000.00 by fixed_allowance
- **Highline Roofing & Sheet Metal**
  - ELD: lump sum with no quantity - cannot check against GC takeoff
  - FLASH: manual override: Flashing marked "Included" with no breakout; estimator judges the included scope insufficient - plugged $100,000.00 by fixed_allowance
  - TRANS: excluded by bidder - plugged $75,000.00 by fixed_allowance
- **Cascade Membrane Systems**
  - RA1: quantity +6.0% vs GC takeoff after converting SF - re-extended, -46,939.86
  - FLUTE: not priced - plugged $8,650.00 by average_of_bidders
- **Tetonview Roofing**
  - RA2: excluded by bidder - plugged $39,442.25 by average_of_bidders
  - ELD: excluded by bidder - plugged $20,939.54 by unit_rate_x_gc_qty

Award by plug method: policy as written: Highline Roofing & Sheet Metal; gc_estimate: Highline Roofing & Sheet Metal; min_of_bidders: Highline Roofing & Sheet Metal; average_of_bidders: Highline Roofing & Sheet Metal; median_of_bidders: Highline Roofing & Sheet Metal; max_of_bidders: Highline Roofing & Sheet Metal.

## 09.67 Fluid-Applied Flooring

| Bidder | File | As bid | Qty adjustments | Plugs + allowances | Total package value |
|---|---|---|---|---|---|
| Granite Peak Floor Coatings **(recommended)** | `Granite Peak - Proposal Fluid Applied Flooring.pdf` | $252,853.00 | $-17,340.00 | $57,000.00 | $297,408.78 |
| Northfork Polishing & Resinous | `Northfork - 09.67 Bid Form.xlsx` | $433,829.75 | $+11,829.51 | $67,000.00 | $521,239.62 |
| Sagebrush Surfaces | `Sagebrush_Surfaces_TCJC_SY_pricing.xlsx` | $268,047.54 | $+0.00 | $150,228.42 | $425,276.63 |
| Bighorn Industrial Floors | `Bighorn floors quote.docx` | $142,816.00 | $+9,884.50 | $155,228.42 | $313,082.71 |

What each bid tests:

- **Granite Peak Floor Coatings**
  - PSC1: quantity +30.3% vs GC takeoff after converting SF - re-extended, -17,340.00
- **Northfork Polishing & Resinous**
  - PSC1: quantity -14.9% vs GC takeoff after converting SF - re-extended, +11,829.51
  - TOP: excluded by bidder - plugged $10,000.00 by gc_estimate
- **Sagebrush Surfaces**
  - TC1: excluded by bidder - plugged $83,228.42 by median_of_bidders
  - TOP: excluded by bidder - plugged $10,000.00 by gc_estimate
- **Bighorn Industrial Floors**
  - RN1: quantity -15.6% vs GC takeoff after converting SF - re-extended, +7,243.50
  - RN2: quantity -17.8% vs GC takeoff after converting SF - re-extended, +2,641.00
  - SC1: lump sum with no quantity - cannot check against GC takeoff
  - TC1: excluded by bidder - plugged $83,228.42 by median_of_bidders
  - MOIST: excluded by bidder - plugged $5,000.00 by min_of_bidders
  - TOP: not priced - plugged $10,000.00 by gc_estimate

Award by plug method: policy as written: Granite Peak Floor Coatings; gc_estimate: Bighorn Industrial Floors; min_of_bidders: Bighorn Industrial Floors; average_of_bidders: Granite Peak Floor Coatings; median_of_bidders: Granite Peak Floor Coatings; max_of_bidders: Granite Peak Floor Coatings.

## 32.90 Landscaping and Irrigation

| Bidder | File | As bid | Qty adjustments | Plugs + allowances | Total package value |
|---|---|---|---|---|---|
| Aspen Hollow Landscapes | `Aspen Hollow - 32.90 Bid Form.xlsx` | $267,978.41 | $-10,437.86 | $13,928.28 | $276,012.40 |
| Elkhorn Grounds & Irrigation | `Elkhorn Grounds Proposal - Justice Center.pdf` | $418,205.37 | $+0.00 | $35,392.60 | $461,189.82 |
| Cutthroat Creek Nursery **(recommended)** | `Cutthroat Creek Nursery bid - landscape.docx` | $188,291.20 | $-826.75 | $0.00 | $190,602.04 |
| Wind River Site Works | `WIND RIVER SITE WORKS - ESTIMATE.xlsx` | $294,518.28 | $+1,733.40 | $57,735.21 | $359,911.56 |

What each bid tests:

- **Aspen Hollow Landscapes**
  - BIKE: quantity -22.2% vs GC takeoff after converting EA - re-extended, +1,737.66
  - SHRUBS: quantity +13.1% vs GC takeoff after converting EA - re-extended, -1,753.84
  - GRASS: quantity +57.4% vs GC takeoff after converting EA - re-extended, -2,805.60
  - PAVERS: quantity +13.0% vs GC takeoff after converting SF - re-extended, -7,616.08
  - SILVA: lump sum with no quantity - cannot check against GC takeoff
  - BENCH47: not priced - plugged $4,844.90 by median_of_bidders
  - DRAIN: excluded by bidder - plugged $2,583.38 by gc_estimate
  - MAINT: excluded by bidder - plugged $6,500.00 by max_of_bidders
- **Elkhorn Grounds & Irrigation**
  - PAVERS: lump sum with no quantity - cannot check against GC takeoff
  - SILVA: excluded by bidder - plugged $26,309.22 by median_of_bidders
  - DRAIN: not priced - plugged $2,583.38 by gc_estimate
  - MAINT: excluded by bidder - plugged $6,500.00 by max_of_bidders
- **Cutthroat Creek Nursery**
  - BIKE: quantity -33.3% vs GC takeoff after converting EA - re-extended, +1,800.00
  - TREES: quantity -11.1% vs GC takeoff after converting EA - re-extended, +3,444.45
  - MMULCH: quantity +10.5% vs GC takeoff after converting CY - re-extended, -260.00
  - WMULCH: quantity -33.3% vs GC takeoff after converting SF - re-extended, +1,658.80
  - PAVERS: quantity +13.1% vs GC takeoff after converting SY - re-extended, -7,470.00
- **Wind River Site Works**
  - SHRUBS: quantity -10.7% vs GC takeoff after converting EA - re-extended, +1,733.40
  - FENCE: lump sum with no quantity - cannot check against GC takeoff
  - PAVERS: excluded by bidder - plugged $57,735.21 by unit_rate_x_gc_qty

Award by plug method: policy as written: Cutthroat Creek Nursery; gc_estimate: Cutthroat Creek Nursery; min_of_bidders: Cutthroat Creek Nursery; average_of_bidders: Cutthroat Creek Nursery; median_of_bidders: Cutthroat Creek Nursery; max_of_bidders: Cutthroat Creek Nursery.

## Regenerating

```
uv run --no-project --with reportlab --with python-docx --with openpyxl --with pypdf --with pyyaml --with google-genai \
    tools/gen_samples/generate.py [--refresh-ai]
```

AI plugs need `GOOGLE_API_KEY` (Vertex AI key) or `GOOGLE_CLOUD_PROJECT` in the environment; set `GEMINI_MODEL` to override the model. Answers are cached in `answer_key/ai_plug_snapshots.json` and reused unless `--refresh-ai` is passed. Without credentials the fallback methods in the policy are used and the answer key says so.
