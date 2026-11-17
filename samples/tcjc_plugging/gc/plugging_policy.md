# Plugging Policy

> SYNTHETIC TEST DOCUMENT. Prose version of `plugging_policy.yaml`; the YAML governs.

## 1. When a plug is applied

A plug is added to a bidder for a scope item when the bidder **excluded** the item or **did not price** it. An item the bidder marks "included" is not plugged unless an estimator records a manual override with a reason.

## 2. Comparable pool

Bidder-based methods use the leveled values of the other bidders for the same item. The bidder being plugged is excluded, and so are unresponsive bidders. When the pool has 3 or more prices, any price more than 50% away from the pool median is dropped. A bidder-based method needs at least 2 prices unless the rule says otherwise; if it has fewer, the next method in the fallback chain is used.

## 3. Methods

| Method | Plug value |
|---|---|
| `gc_estimate` | CM/GC estimate for the item (unit rate x GC quantity, or the lump sum) |
| `min_of_bidders` | Lowest leveled value among comparable bidders |
| `max_of_bidders` | Highest leveled value among comparable bidders |
| `average_of_bidders` | Mean leveled value of comparable bidders |
| `median_of_bidders` | Median leveled value of comparable bidders |
| `unit_rate_x_gc_qty` | rate_source (min | average | median | max of comparable unit rates, or gc) x GC quantity |
| `fixed_allowance` | Stated amount |
| `ai_market_price` | Recent market unit price found by the LLM x GC quantity |

Default rule: `average_of_bidders -> gc_estimate`.

## 4. Rules by package

### 07.50

| Item | Rule (method -> fallbacks) |
|---|---|
| RA2: Roof Assembly RA2 - TPO roof with decorative ballast | `ai_market_price -> average_of_bidders -> gc_estimate` |
| ELD: Electronic leak detection per Section 07 54 23 | `unit_rate_x_gc_qty (rate source: median) -> gc_estimate` |
| FLUTE: Acoustic flute filler at roof deck (install only) | `average_of_bidders -> gc_estimate` |
| TRANS: Transition strips at dissimilar roof assemblies | `fixed_allowance ($75,000)` |
| every other item | default rule |

- Allowance added to every bidder: Additional flashing, $50,000
- Manual override: Highline Roofing & Sheet Metal, FLASH, $100,000. Flashing marked "Included" with no breakout; estimator judges the included scope insufficient.

### 09.67

| Item | Rule (method -> fallbacks) |
|---|---|
| TC1: TC-1 traffic coating | `ai_market_price -> median_of_bidders -> gc_estimate` |
| TOP: Cement topping slab at detention showers (34/AD53) | `average_of_bidders -> gc_estimate` |
| MOIST: Moisture testing | `min_of_bidders (minimum pool 1) -> gc_estimate` |
| every other item | default rule |

- Allowance added to every bidder: Polished concrete touch-ups, $25,000
- Allowance added to every bidder: Joint sealer at sealed concrete, $32,000

### 32.90

| Item | Rule (method -> fallbacks) |
|---|---|
| PAVERS: 1.1 Unit pavers, herringbone pattern | `ai_market_price -> unit_rate_x_gc_qty (rate source: average) -> gc_estimate` |
| SILVA: 0.6 Silva Cell field system | `ai_market_price -> median_of_bidders -> gc_estimate` |
| BENCH47: 4.7 Park bench with dividers | `median_of_bidders -> gc_estimate` |
| DRAIN: Drainage rock at site planter / retaining walls | `average_of_bidders -> gc_estimate` |
| MAINT: One year additional maintenance | `max_of_bidders -> gc_estimate` |
| every other item | default rule |


## 5. Quantity normalization

1. Convert the bid quantity to the GC unit using `unit_conversions.yaml` and any assumption stated in the bid (depth, roll size, panel length).
2. Variance = (converted bid quantity - GC quantity) / GC quantity.
3. If the variance is more than 5% either way, re-extend: leveled value = bidder unit rate in the GC unit x GC quantity. Record the adjustment. Otherwise carry the line as bid.
4. A lump sum with a stated quantity is treated the same way using its implied unit rate.
5. A lump sum with no quantity is carried as bid and flagged.

## 6. AI market price

Provider: Gemini on Vertex AI with Google Search grounding. The model searches for recent installed prices for the item in the region (Mountain West United States (Wyoming / Idaho)), using sources from the last 12 months. It must return a unit price, a low and high, a confidence, and at least 2 sources with URL and date. Plug = unit price x GC quantity.
The AI price is rejected, and the fallback used, when no price is returned, fewer than 2 sources are cited, or confidence is low. An accepted AI plug more than 25% away from the bidders' average for the item is flagged for review. Because web results change, a system is scored as correct when its AI plug is within 25% of the reference value and cites its sources.

## 7. Audit

Every plug records: the reason, the method requested, each method tried and why it was skipped, the pool and any trimmed outliers, the formula and the value.
