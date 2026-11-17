import { short } from '../format'

/** Every bid for one scope item on a single line: where one bidder's price sits within the whole field. */
export function Strip({ result, itemKey, highlightId, height = 104 }: { result: any; itemKey: string; highlightId?: string; height?: number }) {
  const row = result.rows[itemKey]
  const item = result.items.find((i: any) => i.key === itemKey)
  const pts = result.bidders.map((b: any) => ({ b, c: b.cells[itemKey] })).filter((p: any) => p.c.value != null && p.c.value > 0)
  const all = pts.map((p: any) => p.c.value).concat(item.estimate ? [item.estimate] : [])
  if (!all.length) return <p className="muted">No values for this item.</p>
  const W = 400, padL = 14, padR = 14
  let lo = Math.min(...all), hi = Math.max(...all)
  if (hi / lo < 1.08) { lo *= 0.94; hi *= 1.06 }
  const a = Math.log(lo * 0.94), z = Math.log(hi * 1.06)
  const x = (v: number) => padL + ((Math.log(v) - a) / (z - a)) * (W - padL - padR)
  const cy = 54
  const hl = pts.find((p: any) => p.b.id === highlightId)
  return (
    <svg viewBox={`0 0 ${W} ${height}`} width="100%" role="img" aria-label="Position of this price among all bids for the item">
      <line x1={padL} x2={W - padR} y1={cy} y2={cy} stroke="var(--line)" />
      {row.n >= 3 && <rect x={x(row.q1)} y={cy - 12} width={Math.max(2, x(row.q3) - x(row.q1))} height={24} fill="var(--surface-2)" rx={3} />}
      {row.med && <line x1={x(row.med)} x2={x(row.med)} y1={cy - 17} y2={cy + 17} stroke="var(--ink-2)" strokeWidth={1.5} />}
      {row.med && <text x={Math.min(W - 50, Math.max(50, x(row.med)))} y={cy - 22} textAnchor="middle" fontSize={10} fill="var(--ink-2)">median {short(row.med)}</text>}
      {pts.filter((p: any) => p.b.id !== highlightId).map((p: any) =>
        p.c.state === 'plugged'
          ? <path key={p.b.id} d={`M${x(p.c.value)},${cy - 5}l5,5l-5,5l-5,-5Z`} fill="#fff" stroke="var(--plug-ink)" strokeWidth={1.5} opacity={p.b.qualified ? 1 : .5}><title>{p.b.name}: plug {short(p.c.value)}</title></path>
          : <line key={p.b.id} x1={x(p.c.value)} x2={x(p.c.value)} y1={cy - 9} y2={cy + 9} stroke={p.b.qualified ? 'var(--ink)' : 'var(--muted)'} strokeWidth={2} strokeLinecap="round" opacity={p.b.qualified ? .75 : .45}><title>{p.b.name}: {short(p.c.value)}</title></line>)}
      {item.estimate ? <g><path d={`M${x(item.estimate)},${cy + 16}l5,8h-10Z`} fill="var(--ink)" /><text x={Math.min(W - 50, Math.max(50, x(item.estimate)))} y={cy + 38} textAnchor="middle" fontSize={10} fill="var(--ink-2)">GC est. {short(item.estimate)}</text></g> : null}
      {hl && <g>
        <circle cx={x(hl.c.value)} cy={cy} r={7} fill={hl.c.state === 'plugged' ? 'var(--plug-ink)' : 'var(--orange)'} stroke="#fff" strokeWidth={2.5} />
        <text x={Math.min(W - 60, Math.max(60, x(hl.c.value)))} y={12} textAnchor="middle" fontSize={11.5} fontWeight={700} fill="var(--orange-2)">{hl.b.code} · {short(hl.c.value)}</text>
      </g>}
    </svg>
  )
}
