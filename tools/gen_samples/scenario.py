"""Build samples/tcjc_plugging: designed bids + plugging policy + answer key computed by the reference engine."""
import json
import shutil

import yaml
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

import ai_plug
import gc_docs
import plugging
import verify
from render_office import render_docx, render_xlsx
from render_pdf import render_pdf
from specs_plugging import AI_QUERIES, BIDS, CONVERSIONS, ITEMS, POLICY, SYNTHETIC_GC

RENDER = {'pdf': render_pdf, 'docx': render_docx, 'xlsx': render_xlsx}
HDR = PatternFill('solid', fgColor='1F2937')
NOTE = ('SYNTHETIC. GC scope items and quantities are from the TCJC workbook; bidders are fictional and their prices are designed '
        '(mostly real workbook unit rates re-quoted at altered quantities and units; some rates are invented to create specific cases).')


def head(ws, widths):
    for i, w in enumerate(widths):
        ws.column_dimensions[ws.cell(row=1, column=i + 1).column_letter].width = w
        ws.cell(row=1, column=i + 1).font = Font(bold=True, color='FFFFFF')
        ws.cell(row=1, column=i + 1).fill = HDR
    ws.freeze_panes = 'A2'


def rule_text(rule, dflt):
    def one(s):
        s = s if isinstance(s, dict) else {'method': s}
        t = s['method']
        if 'rate_source' in s:
            t += f" (rate source: {s['rate_source']})"
        if 'amount' in s:
            t += f" (${s['amount']:,.0f})"
        if 'min_pool' in s:
            t += f" (minimum pool {s['min_pool']})"
        return t
    chain = [one(dict(rule, method=rule.get('method', dflt['method'])))] + [one(s) for s in rule.get('fallback', dflt['fallback'])]
    if rule.get('method') == 'fixed_allowance':
        chain = chain[:1]
    return ' -> '.join(chain)


def write_policy_files(gc, items):
    d, qn, ai, cp = POLICY['defaults'], POLICY['quantity_normalization'], POLICY['ai_market_price'], POLICY['defaults']['comparable_pool']
    hdr = '# Plugging policy for bid leveling. SYNTHETIC test document.\n# Item keys match the "Key" column of each scope_sheet.xlsx.\n'
    (gc / 'plugging_policy.yaml').write_text(hdr + yaml.safe_dump(POLICY, sort_keys=False, width=110))
    (gc / 'unit_conversions.yaml').write_text('# Unit conversions used when a bid is quoted in a unit other than the GC unit.\n' +
                                               yaml.safe_dump(CONVERSIONS, sort_keys=False, width=110))
    L = ['# Plugging Policy', '', '> SYNTHETIC TEST DOCUMENT. Prose version of `plugging_policy.yaml`; the YAML governs.', '',
         '## 1. When a plug is applied', '',
         'A plug is added to a bidder for a scope item when the bidder **excluded** the item or **did not price** it. '
         'An item the bidder marks "included" is not plugged unless an estimator records a manual override with a reason.', '',
         '## 2. Comparable pool', '',
         f"Bidder-based methods use the leveled values of the other bidders for the same item. The bidder being plugged is excluded, "
         f"and so are unresponsive bidders. When the pool has {cp['outlier_trim_min_pool']} or more prices, any price more than "
         f"{cp['outlier_trim_pct']}% away from the pool median is dropped. A bidder-based method needs at least {cp['min_pool']} "
         f"prices unless the rule says otherwise; if it has fewer, the next method in the fallback chain is used.", '',
         '## 3. Methods', '', '| Method | Plug value |', '|---|---|']
    L += [f'| `{k}` | {v} |' for k, v in POLICY['methods'].items()]
    L += ['', f"Default rule: `{rule_text({}, d)}`.", '', '## 4. Rules by package', '']
    for code, pp in POLICY['packages'].items():
        L += [f'### {code}', '', '| Item | Rule (method -> fallbacks) |', '|---|---|']
        L += [f"| {k}: {items[code][k]['desc']} | `{rule_text(r, d)}` |" for k, r in pp['items'].items()]
        L += ['| every other item | default rule |', '']
        for a in pp['allowances_all_bidders']:
            L.append(f"- Allowance added to every bidder: {a['name']}, ${a['amount']:,.0f}")
        for o in pp.get('manual_overrides', []):
            L.append(f"- Manual override: {o['bidder']}, {o['item']}, ${o['amount']:,.0f}. {o['reason']}.")
        L.append('')
    L += ['## 5. Quantity normalization', '',
          '1. Convert the bid quantity to the GC unit using `unit_conversions.yaml` and any assumption stated in the bid (depth, roll size, panel length).',
          '2. Variance = (converted bid quantity - GC quantity) / GC quantity.',
          f"3. If the variance is more than {qn['threshold_pct']:g}% either way, re-extend: leveled value = bidder unit rate in the GC unit x GC quantity. "
          'Record the adjustment. Otherwise carry the line as bid.',
          '4. A lump sum with a stated quantity is treated the same way using its implied unit rate.',
          '5. A lump sum with no quantity is carried as bid and flagged.', '',
          '## 6. AI market price', '',
          f"Provider: {ai['provider']}. The model searches for recent installed prices for the item in the region ({ai['region']}), "
          f"using sources from the last {ai['recency_months']} months. It must return a unit price, a low and high, a confidence, and at "
          f"least {ai['min_sources']} sources with URL and date. Plug = unit price x GC quantity.",
          f"The AI price is rejected, and the fallback used, when no price is returned, fewer than {ai['min_sources']} sources are cited, or confidence is low. "
          f"An accepted AI plug more than {ai['flag_if_deviation_from_bidder_average_pct']}% away from the bidders' average for the item is flagged for review. "
          f"Because web results change, a system is scored as correct when its AI plug is within {ai['acceptance_band_pct']}% of the reference value and cites its sources.", '',
          '## 7. Audit', '',
          'Every plug records: the reason, the method requested, each method tried and why it was skipped, the pool and any trimmed outliers, the formula and the value.', '']
    (gc / 'plugging_policy.md').write_text('\n'.join(L))


def write_scope_sheet(gc, pkg, items):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Scope Items'
    ws.append(['Key', 'Scope item', 'CM/GC quantity', 'Unit', 'Specified depth (in.)', 'Bidder Qty', 'Bidder Unit', 'Bidder Unit Price',
               'Bidder Value', 'Comments'])
    for it in items.values():
        ws.append([it['key'], it['desc'], it['qty'], it['unit'], it['depth']])
    head(ws, [10, 62, 16, 8, 14, 12, 12, 16, 16, 30])
    ws = wb.create_sheet('Plug Rules')
    ws.append(['Key', 'Scope item', 'Rule (method -> fallbacks)'])
    pp, d = POLICY['packages'][pkg['code']], POLICY['defaults']
    for it in items.values():
        ws.append([it['key'], it['desc'], rule_text(pp['items'].get(it['key'], {}), d)])
    for a in pp['allowances_all_bidders']:
        ws.append(['', f"Allowance, all bidders: {a['name']}", f"fixed_allowance (${a['amount']:,.0f})"])
    head(ws, [10, 62, 70])
    ws = wb.create_sheet('CMGC Estimate (confidential)')
    ws.append(['Key', 'Scope item', 'Qty', 'Unit', 'Unit rate', 'Estimate', 'Source'])
    for it in items.values():
        ws.append([it['key'], it['desc'], it['qty'], it['unit'], it['rate'], it['estimate'], it['source']])
        ws.cell(row=ws.max_row, column=5).number_format = '$#,##0.0000'
        ws.cell(row=ws.max_row, column=6).number_format = '$#,##0.00'
    ws.append(['', 'TOTAL', None, None, None, round(sum(i['estimate'] for i in items.values()), 2)])
    head(ws, [10, 62, 12, 8, 14, 16, 30])
    d = gc / pkg['slug']
    d.mkdir(parents=True, exist_ok=True)
    wb.save(str(d / 'scope_sheet.xlsx'))


def write_prequal(gc, pkgs, bids):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Prequalification'
    ws.append(['Subcontractor (fictional)', 'Bid package', 'Prequalification status', 'Single-project limit ($)', 'SDI enrolled'])
    for b in bids:
        ws.append([b['company'], f"{b['pkg']} {pkgs[b['pkg']]['name']}", 'Approved', 5000000, 'Yes'])
    head(ws, [36, 32, 24, 22, 14])
    wb.save(str(gc / 'subcontractor_prequal.xlsx'))


def write_answer_key(out, pkgs, items, results, sens, trate, sdi, ai_status):
    for code, res in results.items():
        key = dict(package=code, name=pkgs[code]['name'], note=NOTE,
                   rates=dict(textura_pct_of_base_bid=round(trate * 100, 4), sdi_pct_of_subcontract_value=round(sdi * 100, 4)),
                   formulas=dict(base_bid_value='bid_as_submitted + quantity_adjustments + plug_total + allowance_total',
                                 subcontract_value='base_bid_value + textura', total_package_value='subcontract_value + sdi'),
                   gc_items=list(items[code].values()),
                   plug_rules={k: rule_text(POLICY['packages'][code]['items'].get(k, {}), POLICY['defaults']) for k in items[code]},
                   ai_status=ai_status, **res, sensitivity_by_plug_method=sens[code])
        (out / f"{pkgs[code]['slug']}.json").write_text(json.dumps(key, indent=2) + '\n')

    wb = Workbook()
    ws = wb.active
    ws.title = 'Summary'
    ws.append(['Package', 'Bidder', 'Bid as submitted', 'Quantity adjustments', 'Plugs', 'Allowances', 'Base bid value', 'Textura', 'SDI',
               'Total package value', 'Recommended'])
    for code, res in results.items():
        for r in res['bidders']:
            ws.append([f"{code} {pkgs[code]['name']}", r['company'], r['bid_as_submitted'], r['quantity_adjustments'], r['plug_total'],
                       r['allowance_total'], r['base_bid_value'], r['textura'], r['sdi'], r['total_package_value'],
                       'RECOMMENDED' if r['company'] == res['recommended_bidder'] else ''])
            for c in ws[ws.max_row][2:10]:
                c.number_format = '$#,##0.00'
    head(ws, [32, 34, 18, 20, 16, 14, 18, 12, 14, 20, 16])

    ws = wb.create_sheet('Lines')
    ws.append(['Package', 'Bidder', 'Item', 'Status', 'Bid qty', 'Bid unit', 'Bid unit price', 'Bid amount', 'GC qty', 'GC unit',
               'Converted qty', 'Conversion', 'Variance %', 'Unit rate in GC unit', 'Action', 'Leveled value', 'Adjustment'])
    for code, res in results.items():
        for r in res['bidders']:
            for e in r['lines']:
                a = e['as_bid']
                ws.append([code, r['company'], e['item'], e['status'], a['qty'], a['unit'], a['unit_price'], a['amount'], e['gc']['qty'],
                           e['gc']['unit'], e['converted_qty'], e['conversion'], e['variance_pct'], e['unit_rate_in_gc_unit'], e['action'],
                           e['leveled_value'], e['adjustment']])
    head(ws, [9, 32, 10, 10, 10, 9, 14, 14, 10, 8, 13, 44, 11, 16, 38, 14, 13])

    ws = wb.create_sheet('Plugs')
    ws.append(['Package', 'Bidder', 'Item', 'Reason', 'Method requested', 'Method used', 'Methods tried', 'Pool', 'Trimmed outliers',
               'Formula', 'Plug value', 'Flag'])
    for code, res in results.items():
        for r in res['bidders']:
            for p in r['plugs']:
                ws.append([code, r['company'], p['item'], p['reason'], p['method_requested'], p['method_used'],
                           '; '.join(f"{a['method']}: {a['result']}" for a in p['attempts']),
                           '; '.join(f"{x['bidder']} ${x['value']:,.2f}" for x in p['pool']),
                           '; '.join(f"{x['bidder']} ${x['value']:,.2f}" for x in p['trimmed_outliers']), p['formula'], p['value'],
                           p.get('flag', '')])
                ws.cell(row=ws.max_row, column=11).number_format = '$#,##0.00'
            for a in r['allowances']:
                ws.append([code, r['company'], '', 'allowance for all bidders: ' + a['name'], 'fixed_allowance', 'fixed_allowance', '', '', '',
                           'fixed allowance', a['amount'], ''])
    head(ws, [9, 32, 10, 34, 20, 20, 60, 60, 30, 60, 14, 40])

    ws = wb.create_sheet('Sensitivity')
    ws.append(['Package', 'Plug method applied to every gap', 'Recommended bidder', 'Bidder', 'Total package value'])
    for code, s in sens.items():
        for label, v in s.items():
            for comp, tot in v['totals'].items():
                ws.append([code, label, v['recommended_bidder'], comp, tot])
                ws.cell(row=ws.max_row, column=5).number_format = '$#,##0.00'
    head(ws, [9, 34, 34, 34, 20])
    wb.save(str(out / 'answer_key.xlsx'))


def write_readme(out, pkgs, results, sens, ai_status):
    L = ['# TCJC plugging scenario set', '',
         'A second, designed input set for the bid-leveling POC. It exercises a **plugging policy**, **quantity variance** '
         '(a bidder assumed more or less material than the GC) and **unit conversion** (bid unit differs from the GC unit).', '',
         '> ' + NOTE + ' Totals here do not tie to the TCJC workbook; `samples/tcjc/` is the set that does.', '',
         '## Inputs', '',
         '- `gc/plugging_policy.yaml` (+ `.md`): plug methods, per-item rules with fallback chains, comparable pool, quantity normalization, AI method.',
         '- `gc/unit_conversions.yaml`: SQ, SY, m2, CY at depth, rolls, panels.',
         '- `gc/<package>/scope_sheet.xlsx`: scope items with GC quantity and unit, the plug rule per item, confidential GC estimate.',
         '- `gc/awarding_policy.md/.docx`, `gc/project_brief.md`, `gc/subcontractor_prequal.xlsx`.',
         '- `bids/<package>/`: 4 bids per package (PDF, Word, Excel).', '',
         '## Expected results (`answer_key/`)', '',
         '`<package>.json` gives, per bidder and line: as bid, converted quantity, variance, action, leveled value; then each plug with '
         'method requested, methods tried, pool, trimmed outliers, formula and value; totals; and the award under each plug method. '
         '`answer_key.xlsx` shows the same as Summary, Lines, Plugs and Sensitivity sheets.', '',
         f'AI plugs: {ai_status}.', '']
    for code, res in results.items():
        L += [f"## {code} {pkgs[code]['name']}", '', '| Bidder | File | As bid | Qty adjustments | Plugs + allowances | Total package value |', '|---|---|---|---|---|---|']
        for r in res['bidders']:
            star = ' **(recommended)**' if r['company'] == res['recommended_bidder'] else ''
            L.append(f"| {r['company']}{star} | `{r['document']}` | ${r['bid_as_submitted']:,.2f} | ${r['quantity_adjustments']:+,.2f} | "
                     f"${r['plug_total'] + r['allowance_total']:,.2f} | ${r['total_package_value']:,.2f} |")
        L += ['', 'What each bid tests:', '']
        for r in res['bidders']:
            L.append(f"- **{r['company']}**")
            L += [f'  - {f}' for f in r['expected_flags']] or ['  - no adjustments or plugs']
        awards = {label: v['recommended_bidder'] for label, v in sens[code].items()}
        L += ['', 'Award by plug method: ' + '; '.join(f'{k}: {v}' for k, v in awards.items()) + '.', '']
    L += ['## Regenerating', '', '```',
          'uv run --no-project --with reportlab --with python-docx --with openpyxl --with pypdf --with pyyaml --with google-genai \\',
          '    tools/gen_samples/generate.py [--refresh-ai]', '```', '',
          'AI plugs need `GOOGLE_API_KEY` (Vertex AI key) or `GOOGLE_CLOUD_PROJECT` in the environment; set `GEMINI_MODEL` to override the model. '
          'Answers are cached in `answer_key/ai_plug_snapshots.json` and reused unless `--refresh-ai` is passed. Without credentials the '
          'fallback methods in the policy are used and the answer key says so.', '']
    (out / 'README.md').write_text('\n'.join(L))


def build(wb, pkgs, out, refresh_ai=False):
    print(plugging.selftest())
    for sub in ('gc', 'bids'):
        shutil.rmtree(out / sub, ignore_errors=True)
    gc, ak = out / 'gc', out / 'answer_key'
    gc.mkdir(parents=True)
    ak.mkdir(parents=True, exist_ok=True)
    items = {c: plugging.resolve_items(pkgs[c], ITEMS[c], SYNTHETIC_GC) for c in pkgs}
    bids = [plugging.resolve_bid(b, pkgs[b['pkg']], items[b['pkg']]) for b in BIDS]
    files = []
    for b in bids:
        d = out / 'bids' / pkgs[b['pkg']]['slug']
        d.mkdir(parents=True, exist_ok=True)
        RENDER[b['fmt']](b, d / b['file'])
        files.append((b, d / b['file']))

    f, trate = gc_docs.facts(wb), gc_docs.textura_rate(pkgs)
    gc_docs.write_brief(gc, f, trate, pkgs)
    gc_docs.write_policy(gc, f, trate, pkgs, sec5=[
        'Scope gaps, allowances, quantity differences and unit conversions are leveled according to the Plugging Policy '
        '(plugging_policy.yaml and plugging_policy.md), which governs over this section.',
        f'Textura: {trate * 100:.3f}% of Base Bid Value. SDI: {f["sdi_rate"] * 100:.2f}% of Subcontract Value.',
        'Sales tax: the project is tax exempt; bids are leveled exclusive of sales tax.'])
    write_policy_files(gc, items)
    write_prequal(gc, pkgs, bids)
    for c in pkgs:
        write_scope_sheet(gc, pkgs[c], items[c])

    snap_path = ak / 'ai_plug_snapshots.json'
    snaps, ai_status = ai_plug.load_or_fetch(snap_path, AI_QUERIES, items, POLICY['ai_market_price'], refresh_ai)
    if snaps:
        snap_path.write_text(json.dumps(snaps, indent=2) + '\n')
    results, sens = {}, {}
    for c in pkgs:
        mine = [b for b in bids if b['pkg'] == c]
        results[c] = plugging.level(c, mine, items[c], POLICY, trate, f['sdi_rate'], snaps)
        sens[c] = plugging.sensitivity(c, mine, items[c], POLICY, trate, f['sdi_rate'], snaps)
    write_answer_key(ak, pkgs, items, results, sens, trate, f['sdi_rate'], ai_status)
    write_readme(out, pkgs, results, sens, ai_status)

    problems = verify.check_files(files)
    for c, res in results.items():                      # independent recomputation from the JSON on disk
        key = json.loads((ak / f"{pkgs[c]['slug']}.json").read_text())
        for r in key['bidders']:
            lev = sum(e['leveled_value'] or 0 for e in r['lines'])
            base = lev + sum(p['value'] for p in r['plugs']) + sum(a['amount'] for a in r['allowances'])
            if abs(base - r['base_bid_value']) > 0.02 or abs(lev - (r['bid_as_submitted'] + r['quantity_adjustments'])) > 0.02:
                problems.append(f"{c} {r['company']}: leveled lines + plugs do not equal base bid value")
            if any(p['value'] is None for p in r['plugs']):
                problems.append(f"{c} {r['company']}: a gap has no plug value")
        print(f"\n{c} {pkgs[c]['name']}")
        for r in res['bidders']:
            print(f"  {r['company']:<32} bid {r['bid_as_submitted']:>12,.2f}  qty adj {r['quantity_adjustments']:>+11,.2f}  "
                  f"plugs {r['plug_total'] + r['allowance_total']:>11,.2f}  total {r['total_package_value']:>13,.2f}"
                  f"{'  RECOMMENDED' if r['company'] == res['recommended_bidder'] else ''}")
        print('  award by method: ' + '; '.join(f"{k}={v['recommended_bidder']}" for k, v in sens[c].items()))
    print(f'\nAI plugs: {ai_status}')
    return files, problems
