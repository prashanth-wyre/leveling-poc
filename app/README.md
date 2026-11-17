# Wyre bid leveling app (POC)

An AI-native bid leveling tool: upload a scope sheet, an award policy and subcontractor proposals; the app
reads them, normalizes units and quantities, plugs the gaps, scores every bidder against the policy and
explains the result at subcontractor level and at cell level.

## Run it

```
./app/run.sh            # builds the front end, serves everything on http://localhost:8000
./app/run.sh --dev      # API on :8000 with reload, Vite dev server on :5173
```

Needs `uv`, Node and a Gemini key. The key and model are read from the repo-level `.env`
(`GEMINI_KEY`, `GEMINI_MODEL`), which is git-ignored. On start the app adds any missing sample project:

| Project | Packages | Bidders |
|---|---|---|
| Teton County Justice Center | 07.50, 09.67, 32.90 from `samples/tcjc_plugging` | 4 each |
| Teton County Justice Center (workbook bids) | the same packages from `samples/tcjc` (scope read by AI from the scope sheet) | 4 to 6 each |
| Scale test (generated data) | 05.12 structural steel, readings generated directly (no documents) | 50 |
| Teton County Justice Center (20 bidders, complete scope) | 32.90, 33.00, 32.13 from `samples/tcjc_20` | 20 each, plus a superseded quote and a decline |

Data lives in `app/data/` (git-ignored): the SQLite database, uploaded files and the model response cache.
Delete that folder to start clean.

## Screens

| Screen | What it does |
|---|---|
| Projects | Projects and their bid packages, with status and the recommended subcontractor |
| Documents | Upload proposals (PDF, Word, Excel), the award policy, the scope sheet and supporting files. Click a proposal to see what the AI read, line by line, with the source text and confidence |
| Scopes | The baseline items: section, GC quantity, unit, estimate. "Generate from scope sheet" has the AI read them from the uploaded sheet |
| Policy | The **award rule** the AI read from the policy (lowest price or highest score, and any best-value window), and the **ordinals** the AI derived from it: criteria in priority order, a weight for each (sum 100), a rating scale, the policy clause behind each, and the pass/fail rules. Order and weights are editable. Plug settings are here too, including **Auto-estimate plugs with AI** |
| Level | The Bid Level screen in three views: Table, Landscape, Scorecard |

### Level: Table

Matches the Wyre Bid Level layout: frozen baseline items, one column per bidder ordered by rank, the
Recommended / Alternative / Not in top 3 / Did not qualify band, leveled total, percent above the lowest,
base bid and plugs.

Cell indicators:

| Mark | Meaning |
|---|---|
| Blue / grey / red tint | price against the median for that item, 7 steps (toggle: "Colour by price position") |
| `U` | unit normalized (SQ to SF, m2 to SF, CY to SF at depth, rolls, panels...) |
| `Q` | quantity normalized: the bid quantity was over the threshold from the GC takeoff, so the unit rate was applied to the GC quantity |
| Red cross + orange plug | not priced by the bidder, plugged by the GC. A sparkle marks an AI-estimated plug. Hatched background |
| `E` | estimator override |
| Orange dot | the analysis flags something to check (kept to about one cell in eight) |
| Dashed underline | low-confidence reading |

Click a cell for the detail panel: where the value stands among all bids, the AI explanation, the trail
from as-bid to leveled value (unit conversion, quantity adjustment, plug), the plug detail (methods tried,
pool, outliers, AI basis and sources), the source text, and the override actions. Click a bidder header for
the scorecard and the explanation of why it won or lost. Click a scope item for its analysis.

The cell menu (three dots) changes the plug method, marks an item included or not priced, or removes an
override. Every override re-levels the package.

### Level: Landscape and Scorecard

Landscape is the leveling map above the heat grid from `docs/bid-landscape-visualization.md`: qualified
bidders grouped, framed and solid; the rest faded. Scorecard shows every bidder against the weighted ordinals.

## How a leveling run works

| Step | Model (Gemini) | Code |
|---|---|---|
| Extract | reads each proposal against the baseline items: status, quantity, unit, unit price, amount, stated assumptions, conversion factor to the GC unit, source text, confidence; plus inclusions, exclusions, warranty, validity, tax, bidder-added lines | arithmetic checks, revision and decline detection, latest bid per bidder |
| Ordinals | award policy to ordered criteria, weights, rating scales, pass/fail rules, and the award rule | weights normalized to 100; user edits win |
| Normalize | supplies the conversion for units the table does not know | unit conversion, quantity variance against the threshold, re-extension |
| Plug | AI estimate of the unit cost in the GC unit, with range, basis, conversion note and web sources | policy methods (GC estimate, min, max, average, median, unit rate x GC quantity, fixed), fallback chain, outlier trim |
| Assess | decides judgement rules and rates qualitative criteria per bidder, with evidence | price and scope criteria, weighted score, rank; recommendation by the award rule |
| Explain | per-bidder win/lose explanation; per scope item, an analysis of the item and of every bidder's cell | supplies the facts so the text cannot invent numbers; limits how many cells are flagged |

Every model response is cached on disk by content hash, so re-leveling after an override takes a second or
two and the app opens without network access once a package has been leveled. A failed call falls back to
templated text built from the same facts, marked as templated.

## Code

```
app/backend/wyre_level/
  engine.py            deterministic leveling: conversions, normalization, plugs, totals (ported from tools/gen_samples/plugging.py)
  pipeline/extract.py  bid and scope sheet extraction
  pipeline/policy.py   award policy to ordinals
  pipeline/assess.py   AI plug estimate, bidder assessment, scoring
  pipeline/explain.py  cell, scope item and bidder explanations (model + template fallback)
  pipeline/run.py      one leveling run, with progress
  llm.py               Gemini client: schema output, files, web search, cache, timeout
  main.py              HTTP API; serves the built front end
  seed.py              seeds from samples/ and generates the 50-bidder package
  export.py            Excel export
app/backend/tests/     engine and scoring tests
app/backend/eval/      runs the real pipeline on the sample sets and compares with their answer keys
app/frontend/src/
  pages/               Projects, Documents, Scopes, Policy, Level
  level/               BidTable, Panels (cell, bidder, scope item, scorecard), Strip
  landscape/           draw.js (chart code ported from the prototype), Landscape.tsx
```

## Checks

```
cd app/backend
uv run pytest                              # engine and scoring
uv run python eval/run_eval.py scenario    # 12 scenario bids against samples/tcjc_plugging/answer_key
uv run python eval/run_eval.py workbook    # 15 workbook bids against samples/tcjc/answer_key
uv run python eval/run_eval.py twenty      # 66 documents against samples/tcjc_20/answer_key
```

Results of the last evaluation are in `app/EVALUATION.md`.

## Not in this build

Login and multiple users, the Ask Wyre chat, clarification drafting, and the Check and Admin screens
(shown in the navigation, inactive). Fees and insurance (Textura, SDI) are not added to the leveled total,
which follows the Bid Level screenshot: base bid plus plugs.
