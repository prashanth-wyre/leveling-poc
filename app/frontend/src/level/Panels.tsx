import { useState } from 'react'
import { AlertTriangle, Check, ExternalLink, Minus, Plug, Sparkles, Star, X } from 'lucide-react'
import { BAND, day, money, num, pct, signed } from '../format'
import { Strip } from './Strip'

const METHODS: [string, string][] = [
  ['ai_estimate', 'AI estimate'], ['gc_estimate', 'GC estimate'], ['average_of_bidders', 'Average of other bids'], ['median_of_bidders', 'Median of other bids'],
  ['min_of_bidders', 'Lowest of other bids'], ['max_of_bidders', 'Highest of other bids'], ['unit_rate_x_gc_qty', 'Unit rate x GC quantity'],
]

function Ai({ note, children }: { note?: any; children?: any }) {
  return (
    <div className="aibox">
      <div className="hd"><Sparkles size={13} /> {note?.source === 'template' ? 'Analysis (templated)' : 'Wyre AI analysis'}</div>
      {children}
    </div>
  )
}
function Badge({ b }: { b: any }) {
  if (b.band === 'recommended') return <span className="pill lav"><Star size={12} fill="currentColor" /> Recommended · #1</span>
  if (b.band === 'not_qualified') return <span className="pill red"><X size={12} /> Did not qualify</span>
  return <span className={'pill ' + (b.band === 'alternative' ? 'sky' : '')}>{BAND[b.band]} · #{b.rank}</span>
}

// ---------------------------------------------------------------- one data point
export function CellPanel({ result, bidderId, itemKey, onClose, onOverride, busy }: { result: any; bidderId: string; itemKey: string; onClose: () => void; onOverride: (body: any) => void; busy: boolean }) {
  const b = result.bidders.find((x: any) => x.id === bidderId)
  const item = result.items.find((i: any) => i.key === itemKey)
  const [val, setVal] = useState('')
  if (!b || !item) return null
  const c = b.cells[itemKey], row = result.rows[itemKey], ab = c.asBid
  const steps: { t: string; d: string; v?: string; on: boolean }[] = []
  steps.push({
    t: 'As bid', on: c.status === 'priced',
    d: c.status === 'priced' ? [ab.qty != null ? `${num(ab.qty)} ${ab.unit || ''}` : 'Lump sum', ab.unitPrice != null ? `@ ${money(ab.unitPrice, 2)}` : '', ab.description ? `· "${ab.description}"` : ''].filter(Boolean).join(' ')
      : c.status === 'included' ? 'The bid says this is included in another line.' : c.status === 'excluded' ? 'The bid excludes this item.' : 'The bid does not mention this item.',
    v: ab.amount != null ? money(ab.amount, 2) : undefined,
  })
  if (c.unitNorm) steps.push({ t: 'Unit normalization', on: c.unitNorm.applied, d: c.unitNorm.applied ? `${c.unitNorm.explanation}. ${num(ab.qty)} ${ab.unit} = ${num(c.unitNorm.qtyInGcUnit)} ${c.unitNorm.to}, so the rate is ${money(c.unitNorm.rateInGcUnit, 2)}/${c.unitNorm.to}.${c.unitNorm.source === 'llm' ? ' Conversion read by the model from the bid.' : ''}` : `Same unit as the GC (${item.unit}). Rate ${money(c.unitNorm.rateInGcUnit, 2)}/${item.unit}.` })
  if (c.qtyNorm) steps.push({ t: 'Quantity normalization', on: c.qtyNorm.applied, d: `Bid quantity ${num(c.qtyNorm.bidQty)} ${item.unit} against GC takeoff ${num(c.qtyNorm.gcQty)} ${item.unit}: ${pct(c.qtyNorm.variancePct / 100, 1)}. ${c.qtyNorm.applied ? `Over the ${c.qtyNorm.thresholdPct}% threshold, so the unit rate is applied to the GC quantity.` : `Within the ${c.qtyNorm.thresholdPct}% threshold, carried as bid.`}`, v: c.qtyNorm.applied ? signed(c.qtyNorm.adjustment) : undefined })
  if (c.plug) steps.push({ t: `Plug · ${c.plug.label}`, on: true, d: `${c.plug.reason}. ${c.plug.formula}.`, v: money(c.plug.value, 2) })
  if (c.override) steps.push({ t: 'Estimator override', on: true, d: c.override.action === 'manual_value' ? 'Value entered by the estimator.' : c.override.action === 'include' ? 'Marked as included.' : c.override.action === 'exclude' ? 'Marked as not priced.' : `Plug method set to ${c.override.method || 'policy'}.${c.override.note ? ' ' + c.override.note + '.' : ''}` })
  return (
    <aside className="drawer" aria-label="Data point">
      <div className="dh">
        <div>
          <div className="lab" style={{ marginBottom: 4 }}>Data point</div>
          <h3>{item.name}</h3>
          <div className="sub" style={{ marginTop: 2 }}><b>{b.code}</b> · {b.name}</div>
          <div className="row wrap" style={{ marginTop: 8, gap: 6 }}>
            <Badge b={b} />
            {c.unitNorm?.applied && <span className="pill sky">Unit normalized</span>}
            {c.qtyNorm?.applied && <span className="pill lav">Quantity normalized</span>}
            {c.plug && <span className="pill amber"><Plug size={12} /> Plugged{c.plug.method === 'ai_estimate' ? ' by AI' : ''}</span>}
            {c.note?.flag && <span className="pill" style={{ background: 'var(--orange-soft)', color: 'var(--orange-2)' }}>To check</span>}
          </div>
        </div>
        <button className="btn small x" onClick={onClose} aria-label="Close"><X size={15} /></button>
      </div>
      <div className="db">
        <div>
          <dl className="kvs">
            <dt>Leveled value</dt><dd style={{ fontSize: 20 }}>{c.state === 'included' ? 'Included' : money(c.value, 2)}</dd>
            {c.dev != null && <><dt>Against the {row.refKind}</dt><dd>{pct(c.dev, 1)} ({money(row.ref)})</dd></>}
            {c.rank && <><dt>Position in the field</dt><dd>{c.rank} of {c.of} priced, low to high</dd></>}
            <dt>GC estimate</dt><dd>{money(item.estimate)}{item.qty ? ` · ${num(item.qty)} ${item.unit}` : ''}</dd>
          </dl>
        </div>
        <div><h4>Where it stands among all bids</h4><Strip result={result} itemKey={itemKey} highlightId={b.id} /></div>
        <Ai note={c.note}><p>{c.note?.full}</p></Ai>
        <div><h4>How the value was built</h4><div className="trail">{steps.map((s, i) => (
          <div className={'step' + (s.on ? ' on' : '')} key={i}><span className="n">{i + 1}</span><div><div className="t">{s.t}</div><div className="d">{s.d}</div></div><div className="v">{s.v}</div></div>))}</div></div>
        {c.plug && <div><h4>Plug detail</h4>
          <dl className="kvs">
            <dt>Methods tried</dt><dd style={{ fontWeight: 400, textAlign: 'left' }}>{c.plug.attempts.map((a: any) => `${a.label}: ${a.result}`).join(' → ')}</dd>
            {c.plug.pool.length > 0 && <><dt>Comparable prices</dt><dd style={{ fontWeight: 400, textAlign: 'left' }}>{c.plug.pool.map((p: any) => `${p.bidder} ${money(p.value)}`).join(', ')}</dd></>}
            {c.plug.trimmed.length > 0 && <><dt>Left out as outliers</dt><dd style={{ fontWeight: 400, textAlign: 'left' }}>{c.plug.trimmed.map((p: any) => `${p.bidder} ${money(p.value)}`).join(', ')}</dd></>}
          </dl>
          {c.plug.ai && <Ai><p><b>{c.plug.ai.unit_price != null ? `${money(c.plug.ai.unit_price, 2)} per ${item.unit}` : money(c.plug.ai.value)}</b>{c.plug.ai.low != null ? ` (range ${money(c.plug.ai.low)} to ${money(c.plug.ai.high)})` : ''}, confidence {c.plug.ai.confidence}. {c.plug.ai.basis}</p>
            {c.plug.ai.conversion_note && c.plug.ai.conversion_note !== 'none needed' && <p style={{ marginTop: 6 }}><b>Conversion:</b> {c.plug.ai.conversion_note}</p>}
            {c.plug.ai.sources?.length > 0 && <p style={{ marginTop: 6, fontSize: 12.5 }}>Sources: {c.plug.ai.sources.map((s: any, i: number) => <span key={i}>{i > 0 && ', '}<a href={s.url} target="_blank" rel="noreferrer">{s.title || 'source'}</a></span>)}</p>}</Ai>}
        </div>}
        {c.flags?.length > 0 && <div><h4>Checks</h4><div className="checks">{c.flags.map((f: string, i: number) => <div className="c" key={i}><AlertTriangle size={15} style={{ flex: 'none', marginTop: 1 }} />{f}</div>)}</div></div>}
        <div><h4>Source {c.confidence != null && <span className="pill">{Math.round(c.confidence * 100)}% reading confidence</span>}</h4>
          {c.snippet ? <div className="snip">{c.snippet}</div> : <p className="muted">No text in the bid for this item.</p>}
          {c.extractNote && <p className="sub" style={{ marginTop: 6, fontSize: 13 }}>{c.extractNote}</p>}
          {b.document.hasFile && <a className="row" style={{ gap: 6, marginTop: 8, fontSize: 13 }} href={`/api/documents/${b.document.id}/file`} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Open {b.document.filename}</a>}
        </div>
        <div><h4>Override</h4>
          <div className="row wrap" style={{ gap: 8 }}>
            <input className="input small" style={{ width: 130 }} placeholder="Enter a value" inputMode="decimal" value={val} onChange={(e) => setVal(e.target.value)} id="override-value" />
            <button className="btn small" disabled={busy || !val || isNaN(+val.replace(/[$,]/g, ''))} onClick={() => onOverride({ action: 'manual_value', value: +val.replace(/[$,]/g, '') })}>Use value</button>
            <select className="select small" id="override-plug" value="" disabled={busy} onChange={(e) => e.target.value && onOverride({ action: 'plug', method: e.target.value })}>
              <option value="">Plug with…</option>{METHODS.map((m) => <option key={m[0]} value={m[0]}>{m[1]}</option>)}
            </select>
          </div>
          <div className="row wrap" style={{ gap: 8, marginTop: 8 }}>
            <button className="btn small" disabled={busy} onClick={() => onOverride({ action: 'include' })}>Mark included</button>
            <button className="btn small" disabled={busy} onClick={() => onOverride({ action: 'exclude' })}>Mark not priced</button>
            {c.override && <button className="btn small" disabled={busy} onClick={() => onOverride({ action: 'reset' })}>Remove override</button>}
          </div>
          <p className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>An override re-levels the package and is recorded on the cell.</p>
        </div>
      </div>
    </aside>
  )
}

// ---------------------------------------------------------------- one subcontractor
export function BidderPanel({ result, id, onClose }: { result: any; id: string; onClose: () => void }) {
  const b = result.bidders.find((x: any) => x.id === id)
  if (!b) return null
  const e = b.explanation || {}, t = b.terms
  const List = ({ title, items }: { title: string; items?: string[] }) => items?.length ? <div><h4>{title}</h4><ul style={{ margin: 0, paddingLeft: 18, color: 'var(--ink-2)', lineHeight: 1.5 }}>{items.map((x, i) => <li key={i}>{x}</li>)}</ul></div> : null
  return (
    <aside className="drawer" aria-label="Subcontractor">
      <div className="dh">
        <span className="avatar" style={{ width: 34, height: 34, fontSize: 12 }}>{b.code}</span>
        <div><h3>{b.name}</h3><div className="row wrap" style={{ marginTop: 8, gap: 6 }}><Badge b={b} /><span className="pill">Score {b.score.toFixed(1)} / 100</span><span className="pill">{money(b.leveledTotal)}</span></div>
          {b.awardNote && <p className="sub" style={{ marginTop: 6, fontSize: 13 }}>{b.awardNote}.</p>}</div>
        <button className="btn small x" onClick={onClose} aria-label="Close"><X size={15} /></button>
      </div>
      <div className="db">
        <Ai note={e}><p style={{ fontWeight: 700, marginBottom: 6 }}>{e.headline}</p><p>{e.summary}</p>{e.what_would_change && <p style={{ marginTop: 8 }}><b>What would change this:</b> {e.what_would_change}</p>}</Ai>
        <List title="Deciding factors" items={e.deciding_factors} />
        <div className="row" style={{ alignItems: 'flex-start', gap: 20 }}><div style={{ flex: 1 }}><List title="Strengths" items={e.strengths} /></div><div style={{ flex: 1 }}><List title="Weaknesses" items={e.weaknesses} /></div></div>
        <div><h4>Score against the policy ordinals</h4>
          <table className="plain" style={{ fontSize: 13 }}><thead><tr><th>#</th><th>Criterion</th><th className="num">Weight</th><th className="num">Points</th><th className="num">Weighted</th></tr></thead>
            <tbody>{b.ratings.map((r: any) => (
              <tr key={r.criterionId}><td>{r.ordinal}</td><td><b>{r.name}</b><div className="pill" style={{ marginLeft: 6 }}>{r.label}</div><div className="sub" style={{ fontSize: 12.5, marginTop: 4 }}>{r.justification}</div></td>
                <td className="num">{r.weight}%</td><td className="num">{r.points.toFixed(0)}</td><td className="num"><b>{r.weighted.toFixed(1)}</b></td></tr>))}
              <tr><td /><td><b>Total</b></td><td className="num">100%</td><td /><td className="num"><b>{b.score.toFixed(1)}</b></td></tr></tbody></table>
        </div>
        {b.gates.length > 0 && <div><h4>Pass / fail rules</h4><div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>{b.gates.map((g: any) => (
          <div key={g.id} className="row" style={{ alignItems: 'flex-start', gap: 10 }}>
            <span className={'st ' + (g.result === 'pass' ? 'ok' : g.result === 'fail' ? 'x' : 'inc')} style={{ width: 22, height: 22 }}>{g.result === 'pass' ? <Check size={13} /> : g.result === 'fail' ? <X size={13} /> : <Minus size={13} />}</span>
            <div><b>{g.name}</b>{g.result === 'unknown' && <span className="pill" style={{ marginLeft: 6 }}>not enough data</span>}{g.result === 'fail' && g.severity === 'flag' && <span className="pill amber" style={{ marginLeft: 6 }}>flag only</span>}<div className="sub" style={{ fontSize: 12.5 }}>{g.reason}</div></div>
          </div>))}</div></div>}
        <div><h4>From bid to leveled total</h4><dl className="kvs">
          <dt>Total as bid</dt><dd>{money(b.asBid, 2)}</dd>
          <dt>Quantity normalization</dt><dd>{signed(b.quantityAdjustments)}</dd>
          <dt>Base bid</dt><dd>{money(b.baseBid, 2)}</dd>
          <dt>Plugs ({b.counts.plugged} items{b.allowanceTotal ? ' + allowances' : ''})</dt><dd style={{ color: 'var(--orange-2)' }}>+{money(b.plugs, 2)}</dd>
          <dt>Leveled total</dt><dd style={{ fontSize: 18 }}>{money(b.leveledTotal, 2)}</dd>
          <dt>Scope priced by the bidder</dt><dd>{Math.round(b.scopePriced * 100)}%</dd>
          {b.statedTotal != null && <><dt>Total stated in the bid</dt><dd>{money(b.statedTotal, 2)}</dd></>}
        </dl></div>
        {(b.checks.length > 0 || t.redFlags.length > 0) && <div><h4>Checks</h4><div className="checks">{[...b.checks, ...t.redFlags].map((f: string, i: number) => <div className="c" key={i}><AlertTriangle size={15} style={{ flex: 'none', marginTop: 1 }} />{f}</div>)}</div></div>}
        {b.extras?.length > 0 && <div><h4>Other lines in the bid</h4><table className="plain" style={{ fontSize: 13 }}><tbody>{b.extras.map((x: any, i: number) => <tr key={i}><td>{x.description}</td><td><span className="pill">{x.treatment}</span></td><td className="num">{money(x.amount)}</td></tr>)}</tbody></table></div>}
        <List title="Warranty" items={t.warranty} />
        <List title="Exclusions" items={t.exclusions} />
        <List title="Inclusions" items={t.inclusions} />
        <List title="Clarifications" items={t.clarifications} />
        <div><h4>Terms</h4><dl className="kvs">
          <dt>Bid validity</dt><dd>{t.validityDays ? `${t.validityDays} days` : 'Not stated'}</dd>
          <dt>Sales tax</dt><dd>{t.tax === 'included' ? 'Included' : t.tax === 'excluded' ? 'Excluded' : 'Not stated'}</dd>
          <dt>Addenda acknowledged</dt><dd>{t.addenda.length ? t.addenda.join(', ') : 'None stated'}</dd>
          <dt>Document</dt><dd style={{ fontWeight: 400 }}>{b.document.hasFile ? <a href={`/api/documents/${b.document.id}/file`} target="_blank" rel="noreferrer">{b.document.filename}</a> : b.document.filename}{b.document.date ? ` · ${day(b.document.date)}` : ''}</dd>
        </dl></div>
      </div>
    </aside>
  )
}

// ---------------------------------------------------------------- one scope item
export function ItemPanel({ result, itemKey, onClose, onCell }: { result: any; itemKey: string; onClose: () => void; onCell: (bidderId: string) => void }) {
  const item = result.items.find((i: any) => i.key === itemKey)
  if (!item) return null
  const row = result.rows[itemKey]
  const list = [...result.bidders].sort((a: any, b: any) => (a.cells[itemKey].value ?? 1e18) - (b.cells[itemKey].value ?? 1e18))
  return (
    <aside className="drawer" aria-label="Scope item">
      <div className="dh">
        <div><div className="lab" style={{ marginBottom: 4 }}>Scope item · {item.section}</div><h3>{item.name}</h3>
          <div className="row wrap" style={{ marginTop: 8, gap: 6 }}>
            {row.note?.flag && <span className="pill" style={{ background: 'var(--orange-soft)', color: 'var(--orange-2)' }}>To check</span>}
            <span className="pill">{row.n} priced</span>{row.plugged > 0 && <span className="pill amber">{row.plugged} plugged</span>}
            {row.unitNormalized > 0 && <span className="pill sky">{row.unitNormalized} unit normalized</span>}{row.qtyNormalized > 0 && <span className="pill lav">{row.qtyNormalized} quantity normalized</span>}
          </div></div>
        <button className="btn small x" onClick={onClose} aria-label="Close"><X size={15} /></button>
      </div>
      <div className="db">
        <Ai note={row.note}><p style={{ fontWeight: 700, marginBottom: 6 }}>{row.note?.headline}</p><p>{row.note?.full}</p></Ai>
        <div><h4>Every bid for this item</h4><Strip result={result} itemKey={itemKey} /></div>
        <dl className="kvs">
          <dt>GC takeoff</dt><dd>{item.qty ? `${num(item.qty)} ${item.unit}` : 'Lump sum'}{item.depth ? ` at ${item.depth} in.` : ''}</dd>
          <dt>GC estimate</dt><dd>{money(item.estimate)}{item.rate && item.qty ? ` (${money(item.rate, 2)}/${item.unit})` : ''}</dd>
          <dt>Lowest / median / highest</dt><dd>{money(row.min)} / {money(row.med)} / {money(row.max)}</dd>
          <dt>Compared against</dt><dd>{row.refKind} {money(row.ref)}</dd>
        </dl>
        <div><h4>By bidder, low to high</h4>
          <table className="plain" style={{ fontSize: 13 }}><tbody>{list.map((b: any) => { const c = b.cells[itemKey]; return (
            <tr key={b.id} style={{ cursor: 'pointer', opacity: b.qualified ? 1 : .6 }} onClick={() => onCell(b.id)}>
              <td><b>{b.code}</b></td><td>{b.name}{c.unitNorm?.applied && <span className="chip u" style={{ display: 'inline-grid', marginLeft: 6 }}>U</span>}{c.qtyNorm?.applied && <span className="chip q" style={{ display: 'inline-grid', marginLeft: 4 }}>Q</span>}</td>
              <td>{c.state === 'plugged' ? <span className="pill amber">{c.plug.label}</span> : c.state === 'included' ? <span className="pill">Included</span> : null}</td>
              <td className="num">{c.value != null ? money(c.value) : '–'}</td><td className="num">{c.dev != null ? pct(c.dev) : ''}</td></tr>) })}</tbody></table>
        </div>
      </div>
    </aside>
  )
}

// ---------------------------------------------------------------- scorecard view
export function Scorecard({ result, bidders, onBidder }: { result: any; bidders: any[]; onBidder: (id: string) => void }) {
  const crit = result.policy.criteria
  const colors = ['#0b2a4a', '#1b62d1', '#5598e7', '#7c5cff', '#b7a6ff', '#9aa1ad', '#c9ced6']
  return (
    <div className="lvl-scroll">
      <div className="card" style={{ padding: '16px 20px', marginBottom: 18 }}>
        <div className="row" style={{ gap: 10, marginBottom: 6 }}><Sparkles size={16} color="var(--violet)" /><b>Ordinals from the award policy</b></div>
        <p className="sub" style={{ marginBottom: 6, maxWidth: 1100 }}>{result.policy.summary}</p>
        {result.policy.award_rule?.summary && <p style={{ marginBottom: 12 }}><b>Award rule:</b> {result.policy.award_rule.summary}</p>}
        <div className="weightbar">{crit.map((c: any, i: number) => <i key={c.id} style={{ width: c.weight + '%', background: colors[i % colors.length] }} title={`${c.name}: ${c.weight}%`} />)}</div>
        <div className="row wrap" style={{ gap: '6px 18px', marginTop: 10, fontSize: 12.5 }}>{crit.map((c: any, i: number) => <span key={c.id} className="row" style={{ gap: 6 }}><i style={{ width: 10, height: 10, borderRadius: 2, background: colors[i % colors.length], display: 'inline-block' }} />{c.ordinal}. {c.name} <b>{c.weight}%</b></span>)}</div>
      </div>
      <div className="card" style={{ overflowX: 'auto' }}>
        <table className="plain">
          <thead><tr><th>Rank</th><th>Subcontractor</th><th className="num">Score</th><th style={{ minWidth: 150 }} />{crit.map((c: any) => <th key={c.id} className="num" title={c.how_scored}>{c.ordinal}. {c.name}<br /><span style={{ fontWeight: 400 }}>{c.weight}%</span></th>)}<th className="num">Leveled total</th><th>Rules</th></tr></thead>
          <tbody>{bidders.map((b) => (
            <tr key={b.id} style={{ cursor: 'pointer', background: b.band === 'recommended' ? 'var(--lav)' : undefined, opacity: b.qualified ? 1 : .62 }} onClick={() => onBidder(b.id)}>
              <td>{b.band === 'recommended' ? <span className="pill lav"><Star size={12} fill="currentColor" /> #1</span> : b.rank ? `#${b.rank}` : <span className="pill red">Out</span>}</td>
              <td style={{ minWidth: 300 }}><div className="row" style={{ gap: 10 }}><span className="avatar">{b.code}</span><div><b>{b.name}</b><div className="sub" style={{ fontSize: 12.5, maxWidth: 380 }}>{b.explanation?.headline}</div></div></div></td>
              <td className="num"><b style={{ fontSize: 17 }}>{b.score.toFixed(1)}</b></td>
              <td><div className="weightbar" style={{ height: 10 }}>{b.ratings.map((r: any, i: number) => <i key={r.criterionId} style={{ width: r.weighted + '%', background: colors[i % colors.length] }} title={`${r.name}: ${r.weighted.toFixed(1)} of ${r.weight}`} />)}</div></td>
              {crit.map((c: any) => { const r = b.ratings.find((x: any) => x.criterionId === c.id); return <td key={c.id} className="num" title={r?.justification}>{r ? <><b>{r.points.toFixed(0)}</b><div className="sub" style={{ fontSize: 12 }}>{r.label}</div></> : ''}</td> })}
              <td className="num">{money(b.leveledTotal)}</td>
              <td style={{ maxWidth: 260 }}>{b.reasons.length ? <span style={{ color: 'var(--red)', fontSize: 12.5 }}>{b.reasons.join(' ')}</span> : b.warnings.length ? <span className="sub" style={{ fontSize: 12.5 }}>{b.warnings.length} to confirm</span> : <span className="pill green"><Check size={12} /> All pass</span>}</td>
            </tr>))}</tbody>
        </table>
      </div>
    </div>
  )
}
