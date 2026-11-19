# leveling-poc

AI-native construction bid leveling proof of concept.

| Path | What it is |
|---|---|
| `app/` | The bid leveling app (React front end, Python API, Gemini). Start with `./app/run.sh`; see `app/README.md` and `app/EVALUATION.md` |
| `samples/tcjc/` | Sample inputs reverse-engineered from the TCJC leveling workbook: 14 bids, GC documents, answer key |
| `samples/tcjc_plugging/` | Designed scenario set: plugging policy, quantity variance, unit conversions, answer key |
| `samples/tcjc_20/` | Three packages on their complete workbook scope, 20 subcontractors each (66 documents), with answer keys and qualification facts |
| `tools/gen_samples/` | Generators for the sample sets (`generate.py`, `twenty.py`) and the reference plugging engine |
| `docs/bid-landscape-visualization.md` | Specification of the leveling map and heat grid |
| `prototypes/bid-landscape/` | The visualization prototype the spec was written from |
| `data/` | The source TCJC workbook |

## Streamlit bid day simulator

[Installation and first run](simulator/README.md) · [Illustrated usage guide (PDF)](docs/Bid-Leveling-Simulator-User-Guide.pdf)
