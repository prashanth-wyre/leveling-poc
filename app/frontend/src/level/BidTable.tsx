import { Fragment, useState } from 'react'
import { ArrowDownRight, Check, ChevronDown, ChevronRight, EllipsisVertical, FileText, Link2, Plug, Plus, Sparkles, Star, X } from 'lucide-react'
import { useTip } from '../components/Tip'
import { BAND, day, money, pct, signed } from '../format'

export type Sel = { type: 'cell'; bidderId: string; key: string } | { type: 'bidder'; id: string } | { type: 'item'; key: string } | null

function CellTip({ result, b, k }: { result: any; b: any; k: string }) {
  const c = b.cells[k], item = result.items.find((i: any) => i.key === k), row = result.rows[k]
  const rows: [string, string][] = []
  if (c.value != null) rows.push(['Leveled value', money(c.value)])
  if (c.dev != null) rows.push([`vs ${row.refKind}`, pct(c.dev)])
  if (c.rank) rows.push(['Position', `${c.rank} of ${c.of} priced (low to high)`])
  if (c.asBid.amount != null && c.asBid.amount !== c.value) rows.push(['As bid', money(c.asBid.amount)])
  if (c.asBid.qty != null) rows.push(['Bid quantity', `${c.asBid.qty.toLocaleString()} ${c.asBid.unit || ''}`])
  if (c.unitNorm?.applied) rows.push(['Unit normalized', `${c.unitNorm.from} to ${c.unitNorm.to} (x${+c.unitNorm.factor.toFixed(4)})`])
  if (c.qtyNorm?.applied) rows.push(['Quantity normalized', `${pct(c.qtyNorm.variancePct / 100, 1)} vs GC, ${signed(c.qtyNorm.adjustment)}`])
  if (c.plug) rows.push(['Plug', c.plug.label])
  return (
    <div>
      <div className="tt">{item.name}</div>
      <div className="sub">{b.code} · {b.name}{b.qualified ? '' : ' (did not qualify)'}</div>
      <table><tbody>{rows.map((r) => <tr key={r[0]}><td>{r[0]}</td><td>{r[1]}</td></tr>)}</tbody></table>
      {c.note?.short && <div className="tnote">{c.note.short}</div>}
    </div>
  )
}

export function BidTable({ result, bidders, items, tint, sel, onSel, onMenu, onAddItem }: {
  result: any; bidders: any[]; items: Set<string>; tint: boolean; sel: Sel; onSel: (s: Sel) => void
  onMenu: (e: React.MouseEvent, bidderId: string, key: string) => void; onAddItem: () => void
}) {
  const tip = useTip()
  const [closed, setClosed] = useState<Record<string, boolean>>({})
  const byKey: Record<string, any> = Object.fromEntries(result.items.map((i: any) => [i.key, i]))
  const hasExtras = bidders.some((b) => b.extras?.some((e: any) => e.treatment === 'add' || e.treatment === 'credit'))
  const cols = bidders.length
  return (
    <div className="grid-wrap">
      <table className="bid">
        <thead>
          <tr>
            <th className="base">
              <div className="base-h"><b>Baseline items</b><button className="btn small" onClick={onAddItem}><Plus size={14} /> Add <ChevronDown size={14} /></button></div>
              <div className="muted" style={{ fontSize: 12.5, marginTop: 10 }}>{result.items.length} items</div>
            </th>
            <th className="gutter" />
            {bidders.map((b) => (
              <th key={b.id} className={'bh ' + b.band}>
                <div className="band">
                  {b.band === 'recommended' ? <span className="row" style={{ gap: 6 }}><Star size={13} fill="currentColor" /> Recommended by Wyre</span>
                    : b.band === 'alternative' ? <span>Alternative</span>
                    : b.band === 'other' ? <span>Not in Wyre AI's top 3</span>
                    : <span className="row" style={{ gap: 6 }}><X size={13} /> Did not qualify</span>}
                  <span>{b.band === 'recommended' ? '#1 Top pick' : b.rank ? `#${b.rank}` : ''}</span>
                </div>
                <div className="body" onClick={() => onSel({ type: 'bidder', id: b.id })} title="Open the scorecard and explanation">
                  <div className="who"><span className="avatar">{b.code}</span><span className="nm">{b.name}</span></div>
                  <div className="src"><FileText size={14} /><span className="fn">{b.document.filename}</span>{b.document.date && <span>· {day(b.document.date)}</span>}<span className="lev">Leveled</span></div>
                  <div className="tot"><b>{money(b.leveledTotal)}</b>{b.isLow ? <span className="low"><ArrowDownRight size={13} /> Low</span> : b.pctAboveLow != null ? <span className="pct">+{b.pctAboveLow}%</span> : null}</div>
                  <div className="kv"><span>{money(b.baseBid)}</span><span>Base bid</span></div>
                  <div className="kv plug"><span>{b.plugs ? '+' + money(b.plugs) : '$0'}</span><span>Plugs</span></div>
                  <div className="meta">
                    <span className="pill" title="Weighted score against the policy ordinals">Score {b.score.toFixed(1)}</span>
                    {b.counts.unitNormalized > 0 && <span className="pill sky" title="Cells where the unit was normalized">{b.counts.unitNormalized} unit</span>}
                    {b.counts.qtyNormalized > 0 && <span className="pill lav" title="Cells re-extended to the GC quantity">{b.counts.qtyNormalized} qty</span>}
                    {b.counts.plugged > 0 && <span className="pill amber" title="Cells plugged by the GC">{b.counts.plugged} plug{b.counts.plugged > 1 ? 's' : ''}{b.counts.aiPlugs > 0 ? ` · ${b.counts.aiPlugs} AI` : ''}</span>}
                  </div>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.sections.map((sec: any) => {
            const keys = sec.keys.filter((k: string) => items.has(k))
            if (!keys.length) return null
            const shut = closed[sec.name]
            return (
              <Fragment key={sec.name}>
                <tr className="sec">
                  <td className="base" onClick={() => setClosed({ ...closed, [sec.name]: !shut })}>
                    <div className="name">{shut ? <ChevronRight size={14} /> : <ChevronDown size={14} />}{sec.name}<span className="count">{keys.length}</span></div>
                  </td>
                  <td className="gutter" /><td colSpan={cols} />
                </tr>
                {!shut && keys.map((k: string) => {
                  const row = result.rows[k]
                  return (
                    <tr className="item" key={k}>
                      <td className="base" onClick={() => onSel({ type: 'item', key: k })}
                        onMouseMove={(e) => tip.show(e, <div><div className="tt">{byKey[k].name}</div><div className="sub">{row.n} priced · median {money(row.med)} · GC estimate {money(byKey[k].estimate)}</div><div className="tnote">{row.note?.short}</div></div>)}
                        onMouseLeave={tip.hide}>
                        <div className="nm">{row.note?.flag && <i className="flagdot" />}<span>{byKey[k].name}</span></div>
                      </td>
                      <td className="gutter" />
                      {bidders.map((b) => {
                        const c = b.cells[k]
                        const isSel = sel?.type === 'cell' && sel.bidderId === b.id && sel.key === k
                        const cls = ['cell', c.state, isSel ? 'sel' : '', !b.qualified ? 'dim' : '', tint && c.state === 'priced' && c.cls != null ? `tint c${c.cls}` : ''].join(' ')
                        return (
                          <td key={b.id} className={cls} onClick={() => onSel({ type: 'cell', bidderId: b.id, key: k })}
                            onMouseMove={(e) => tip.show(e, <CellTip result={result} b={b} k={k} />)} onMouseLeave={tip.hide}>
                            <div className="cell-in">
                              <button className="kebab" aria-label="Cell actions" onClick={(e) => { e.stopPropagation(); tip.hide(); onMenu(e, b.id, k) }}><EllipsisVertical size={14} /></button>
                              {c.state === 'priced' && <span className="st ok"><Check size={15} /></span>}
                              {c.state === 'included' && <span className="st inc"><Link2 size={14} /></span>}
                              {c.state === 'plugged' && <><span className="st x"><X size={15} /></span><span className="st plug"><Plug size={14} />{c.plug?.method === 'ai_estimate' && <Sparkles className="spark" size={12} />}</span></>}
                              {c.unitNorm?.applied && <span className="chip u">U</span>}
                              {c.qtyNorm?.applied && <span className="chip q">Q</span>}
                              {c.override && <span className="chip o" title="Estimator override">E</span>}
                              {c.note?.flag && <i className="flagdot" />}
                              {c.state === 'included' ? <span className="amt inc">Included</span>
                                : <span className={'amt' + (c.state === 'plugged' ? ' plugv' : '') + (c.confidence != null && c.confidence < 0.7 ? ' lowconf' : '')}>{money(c.value)}</span>}
                            </div>
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
                <tr className="total">
                  <td className="base">{sec.name} total</td><td className="gutter" />
                  {bidders.map((b) => <td key={b.id} className="v">{money(sec.keys.reduce((s: number, k: string) => s + (b.cells[k].value || 0), 0))}</td>)}
                </tr>
              </Fragment>
            )
          })}
          {hasExtras && (
            <tr className="total">
              <td className="base" title="Priced lines in the bid that are not baseline items: mobilization, freight, credits">Other bid lines</td><td className="gutter" />
              {bidders.map((b) => <td key={b.id} className="v" style={{ fontWeight: 400 }}>{b.extrasTotal ? money(b.extrasTotal) : '–'}</td>)}
            </tr>
          )}
          {result.allowances.map((a: any) => (
            <tr className="total" key={a.name}>
              <td className="base">GC allowance: {a.name}</td><td className="gutter" />
              {bidders.map((b) => <td key={b.id} className="v" style={{ fontWeight: 400, color: 'var(--orange-2)' }}>{money(a.amount)}</td>)}
            </tr>
          ))}
          <tr className="total grand">
            <td className="base">Leveled total</td><td className="gutter" />
            {bidders.map((b) => <td key={b.id} className="v">{money(b.leveledTotal)}</td>)}
          </tr>
        </tbody>
      </table>
    </div>
  )
}
export { BAND }
