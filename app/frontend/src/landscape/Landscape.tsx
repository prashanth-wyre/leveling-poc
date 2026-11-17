import { useLayoutEffect, useRef, useState } from 'react'
import { useTip } from '../components/Tip'
import { money, pct } from '../format'
import type { Sel } from '../level/BidTable'
// @ts-ignore: plain JS module ported from the prototype
import { configure, drawHeat, drawMap, viewState } from './draw.js'

/** Shape the leveling result into the model the chart code draws from. */
function buildModel(result: any, shown: any[]) {
  const byKey: Record<string, any> = Object.fromEntries(result.items.map((i: any) => [i.key, i]))
  const keys: string[] = result.sections.flatMap((s: any) => s.keys)
  const sections: any[] = []
  let first = 0
  result.sections.forEach((s: any) => { sections.push({ name: s.name, first, count: s.keys.length }); first += s.keys.length })
  const secOf: Record<string, number> = {}
  result.sections.forEach((s: any, si: number) => s.keys.forEach((k: string) => { secOf[k] = si }))
  const rows = keys.map((k) => {
    const r = result.rows[k], it = byKey[k]
    const ref = r.ref || it.estimate || r.med || 1
    return { ...r, ref, est: it.estimate || ref, med: r.med ?? ref, q1: r.q1 ?? ref, q3: r.q3 ?? ref, min: r.min ?? ref, max: r.max ?? ref, refName: 'the ' + r.refKind,
      note: r.note || { headline: '', short: '', full: '', flag: false } }
  })
  const items = keys.map((k, i) => ({ i, key: k, name: byKey[k].name, est: rows[i].est, sec: secOf[k], secName: byKey[k].section }))
  const wsum = rows.reduce((a, r) => a + (r.med || 0), 0) || 1
  const map = (b: any) => ({
    id: b.id, code: b.code, name: b.name, qualified: b.qualified, why: b.reasons, rank: b.rank, asbid: b.asBid, adj: b.quantityAdjustments, plugs: b.plugs,
    lev: b.leveledTotal, cov: b.scopePriced,
    cells: keys.map((k) => {
      const c = b.cells[k]
      return { st: c.state === 'plugged' ? 'plug' : c.state === 'included' ? 'incl' : c.qtyNorm?.applied ? 'adj' : 'ok', v: c.value, asbid: c.asBid.amount,
        dev: c.dev ?? 0, cls: c.cls ?? 3, unit: !!c.unitNorm?.applied, note: c.note || { short: '', flag: false } }
    }),
  })
  // qualified first (by rank), then the rest by leveled total: the order the spec asks for
  const order = [...shown].sort((a, b) => (Number(b.qualified) - Number(a.qualified)) || ((a.rank ?? 999) - (b.rank ?? 999)) || (a.leveledTotal - b.leveledTotal)).map(map)
  const gate = result.policy.gates.find((g: any) => g.check === 'scope_priced_min_pct' && g.threshold)
  const estTotal = items.reduce((a, it) => a + it.est, 0)
  return { sc: { sections }, items, rows, all: order, bidders: order, order, rec: order.find((b) => b.id === result.recommendedId) || null, estTotal,
    maxLev: Math.max(...order.map((b) => b.lev), estTotal), weights: rows.map((r) => (r.med || 0) / wsum), nQual: order.filter((b) => b.qualified).length,
    grouped: true, covMin: gate ? gate.threshold / 100 : null }
}

export function Landscape({ result, bidders, sel, onSel }: { result: any; bidders: any[]; sel: Sel; onSel: (s: Sel) => void }) {
  const tip = useTip()
  const mapRef = useRef<HTMLDivElement>(null), gridRef = useRef<HTMLDivElement>(null), rootRef = useRef<HTMLDivElement>(null)
  const [rowMode, setRowMode] = useState<'equal' | 'weight'>('equal')
  const [notes, setNotes] = useState(true)
  const [tick, setTick] = useState(0)
  const [width, setWidth] = useState(0)
  const wrap = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    if (!wrap.current) return
    const ro = new ResizeObserver((e) => setWidth(Math.round(e[0].contentRect.width)))
    ro.observe(wrap.current)
    return () => ro.disconnect()
  }, [])
  useLayoutEffect(() => {
    if (!mapRef.current || !gridRef.current || !width || !bidders.length) return
    const M = buildModel(result, bidders)
    const byId: Record<string, any> = Object.fromEntries(result.bidders.map((b: any) => [b.id, b]))
    const keyIndex = (k: string) => M.items.findIndex((i) => i.key === k)
    configure(
      { sel: sel?.type === 'bidder' ? sel.id : sel?.type === 'cell' ? sel.bidderId : null, cell: sel?.type === 'cell' ? { id: sel.bidderId, i: keyIndex(sel.key) } : null,
        notes: notes ? 'on' : 'off', rowMode },
      {
        onCell: (id: string, key: string) => onSel({ type: 'cell', bidderId: id, key }),
        onBidder: (id: string) => onSel({ type: 'bidder', id }),
        hideTip: tip.hide,
        rerender: () => setTick((t) => t + 1),
        cellTip: (ev: MouseEvent, id: string, key: string) => {
          const b = byId[id], c = b.cells[key], it = result.items.find((i: any) => i.key === key), row = result.rows[key]
          tip.show(ev, <div><div className="tt">{it.name}</div><div className="sub">{b.code} · {b.name}{b.qualified ? '' : ' (did not qualify)'}</div>
            <table><tbody>
              {c.value != null && <tr><td>Leveled value</td><td>{money(c.value)}</td></tr>}
              {c.dev != null && <tr><td>vs {row.refKind}</td><td>{pct(c.dev)}</td></tr>}
              {c.unitNorm?.applied && <tr><td>Unit normalized</td><td>{c.unitNorm.from} to {c.unitNorm.to}</td></tr>}
              {c.qtyNorm?.applied && <tr><td>Quantity normalized</td><td>{pct(c.qtyNorm.variancePct / 100, 1)} vs GC</td></tr>}
              {c.plug && <tr><td>Plug</td><td>{c.plug.label}</td></tr>}
            </tbody></table>{c.note?.short && <div className="tnote">{c.note.short}</div>}</div>)
        },
        bidderTip: (ev: MouseEvent, id: string) => {
          const b = byId[id]
          tip.show(ev, <div><div className="tt">{b.code} · {b.name}</div><div className="sub">{b.qualified ? (b.rank === 1 ? 'Recommended: highest weighted score' : `Qualified, rank ${b.rank}`) : 'Did not qualify: ' + b.reasons.join(' ')}</div>
            <table><tbody><tr><td>Score</td><td>{b.score.toFixed(1)}</td></tr><tr><td>Leveled total</td><td>{money(b.leveledTotal)}</td></tr><tr><td>As bid</td><td>{money(b.asBid)}</td></tr>
              <tr><td>Quantity normalization</td><td>{money(b.quantityAdjustments)}</td></tr><tr><td>Plugs</td><td>{money(b.plugs)}</td></tr><tr><td>Scope priced</td><td>{Math.round(b.scopePriced * 100)}%</td></tr></tbody></table></div>)
        },
        rowTip: (ev: MouseEvent, key: string) => {
          const it = result.items.find((i: any) => i.key === key), row = result.rows[key]
          tip.show(ev, <div><div className="tt">{it.name}</div><div className="sub">Scope item. Click for the full analysis.</div><div className="tnote">{row.note?.short}</div></div>)
        },
      },
    )
    const vs: any = viewState()
    if (vs.openItem != null && vs.openItem >= M.items.length) vs.openItem = null
    // hold the height and the scroll position across the rebuild, so a click never makes the view jump
    const top = rootRef.current?.scrollTop ?? 0, left = gridRef.current.scrollLeft
    mapRef.current.style.minHeight = mapRef.current.offsetHeight + 'px'
    gridRef.current.style.minHeight = gridRef.current.offsetHeight + 'px'
    mapRef.current.textContent = ''
    gridRef.current.textContent = ''
    const api: { grid: any; map: any } = { grid: null, map: null }
    api.map = drawMap(M, mapRef.current, { compact: true, onHover: (id: string) => api.grid?.highlight(id) })
    api.grid = drawHeat(M, gridRef.current, { onHover: (id: string) => api.map?.highlight(id) })
    mapRef.current.style.minHeight = ''
    gridRef.current.style.minHeight = ''
    if (rootRef.current) rootRef.current.scrollTop = top
    gridRef.current.scrollLeft = left
  }, [result, bidders, sel, rowMode, notes, tick, width, tip, onSel])

  return (
    <div className="lvl-scroll" ref={rootRef}>
      <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
        <defs><pattern id="plug-hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="5" height="5" style={{ fill: 'var(--plug-bg)' }} /><rect width="1.6" height="5" style={{ fill: 'var(--plug-ink)' }} /></pattern></defs>
      </svg>
      <div className="row wrap" style={{ marginBottom: 6 }}>
        <div className="legend" style={{ padding: 0 }}>
          <span className="k"><svg width="34" height="14"><rect x="1" y="1" width="14" height="12" rx="2" className="d1" /><rect x="18" y="1" width="14" height="12" rx="2" className="d5" /></svg>Qualified: solid, marked ✓</span>
          <span className="k"><svg width="34" height="14"><rect x="1" y="4" width="14" height="6" className="d1 nq" /><rect x="18" y="4" width="14" height="6" className="d5 nq" /></svg>Did not qualify: faded</span>
          <span className="k"><svg width="18" height="14"><rect x="1" y="1" width="16" height="12" rx="2" className="plug" /></svg>Plugged</span>
          <span className="k"><svg width="18" height="14"><rect x="1" y="1" width="16" height="12" rx="2" className="d2" /><path d="M1,1H7L1,7Z" className="t2" /></svg>Unit normalized</span>
          <span className="k"><svg width="18" height="14"><rect x="1" y="1" width="16" height="12" rx="2" className="d2" /><path d="M11,1H17V7Z" className="t2" /></svg>Quantity normalized</span>
          <span className="k"><svg width="18" height="14"><rect x="1" y="1" width="16" height="12" rx="2" className="d5" /><circle cx="9" cy="7" r="2.4" className="t5" /></svg>To check</span>
        </div>
        <span className="spacer" />
        <div className="seg"><button className={rowMode === 'equal' ? 'on' : ''} onClick={() => setRowMode('equal')}>Equal rows</button><button className={rowMode === 'weight' ? 'on' : ''} onClick={() => setRowMode('weight')}>Rows by dollar weight</button></div>
        <label className="switch"><input type="checkbox" checked={notes} onChange={(e) => setNotes(e.target.checked)} id="ls-notes" /><i />Scope item analysis</label>
      </div>
      <div ref={wrap} className="viz">
        <div className="sublab">Leveling map: who qualifies, and what leveling did to each total</div>
        <div ref={mapRef} />
        <div className="sublab" style={{ marginTop: 20 }}>Heat grid: every scope item for every bidder</div>
        <div ref={gridRef} style={{ overflowX: 'auto' }} />
      </div>
    </div>
  )
}
