"""Generate the TCJC sample input set.

    uv run --no-project --with reportlab --with python-docx --with openpyxl --with pypdf --with pyyaml --with google-genai \
        tools/gen_samples/generate.py [--refresh-ai]

Reads data/TCJC_CD_Estimate Summary_251211.xlsm. Writes samples/tcjc/ (ties to the workbook) and
samples/tcjc_plugging/ (designed plugging / quantity / unit-conversion scenarios).
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import answer_key  # noqa: E402
import gc_docs  # noqa: E402
import scenario  # noqa: E402
import verify  # noqa: E402
from model import load_package, resolve  # noqa: E402
from render_office import render_docx, render_xlsx  # noqa: E402
from render_pdf import render_pdf  # noqa: E402
from specs import BIDS, DECLINES, PACKAGES  # noqa: E402
from tcjc import Workbook  # noqa: E402

ROOT = HERE.parent.parent
SRC = ROOT / 'data' / 'TCJC_CD_Estimate Summary_251211.xlsm'
OUT = ROOT / 'samples' / 'tcjc'
RENDER = {'pdf': render_pdf, 'docx': render_docx, 'xlsx': render_xlsx}


def main():
    wb = Workbook(SRC)
    pkgs = {c: load_package(wb, c, s) for c, s in PACKAGES.items()}
    bids = [resolve(b, pkgs[b['pkg']]) for b in BIDS]

    for sub in ('gc', 'bids', 'answer_key'):
        shutil.rmtree(OUT / sub, ignore_errors=True)
    files = []
    for b in bids + DECLINES:
        d = OUT / 'bids' / pkgs[b['pkg']]['slug']
        d.mkdir(parents=True, exist_ok=True)
        RENDER[b['fmt']](b, d / b['file'])
        files.append((b, d / b['file']))

    gc = OUT / 'gc'
    gc.mkdir(parents=True, exist_ok=True)
    f, trate = gc_docs.facts(wb), gc_docs.textura_rate(pkgs)
    gc_docs.write_brief(gc, f, trate, pkgs)
    gc_docs.write_policy(gc, f, trate, pkgs)
    gc_docs.write_prequal(gc, pkgs)
    gc_docs.write_clarifications(gc, pkgs)
    for p in pkgs.values():
        gc_docs.write_scope_sheet(gc, p)
    keys = answer_key.write(OUT / 'answer_key', pkgs, bids, DECLINES)

    problems = verify.run(files, keys, pkgs)
    for c, key in keys.items():
        print(f"\n{c} {key['name']}  (CM/GC estimate ${key['cmgc_estimate']['total']:,.2f})")
        for e in key['bidders']:
            if e['status'] == 'declined':
                print(f"  {e['company']:<34} declined")
                continue
            tag = 'RECOMMENDED' if e['company'] == key['recommended_bidder'] else '' if e['responsive'] else 'UNRESPONSIVE'
            print(f"  {e['company']:<34} bid {e['sub_bid_as_submitted']:>12,.2f}  plugs {e['gc_plug_total']:>11,.2f}  "
                  f"total {e['total_package_value']:>13,.2f}  {tag}")
    print(f'\n{len(files)} bid documents written to {OUT}')

    print('\n=== Scenario set 2: plugging policy, quantity variance, unit conversion ===')
    files2, problems2 = scenario.build(wb, pkgs, ROOT / 'samples' / 'tcjc_plugging', refresh_ai='--refresh-ai' in sys.argv)
    print(f'{len(files2)} bid documents written to samples/tcjc_plugging')
    problems += problems2
    if problems:
        print('\nVERIFICATION FAILED:\n  ' + '\n  '.join(problems))
        sys.exit(1)
    print('Verification passed: every amount found again in its file; set 1 ties to the workbook; set 2 totals recompute from the answer key.')


if __name__ == '__main__':
    main()
