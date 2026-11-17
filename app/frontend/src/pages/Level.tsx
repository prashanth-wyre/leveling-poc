import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams, Link, useSearchParams } from 'react-router-dom'
import { Clock, FileUp, LayoutGrid, ListChecks, Map as MapIcon, Search, Sparkles, Upload, Wand2 } from 'lucide-react'
import { Shell } from '../components/Shell'
import { post, upload } from '../api'
import { useResource, useRun } from '../hooks'
import { when } from '../format'
import { BidTable, type Sel } from '../level/BidTable'
import { BidderPanel, CellPanel, ItemPanel, Scorecard } from '../level/Panels'
import { Landscape } from '../landscape/Landscape'

const PLUG_METHODS: [string, string][] = [['ai_estimate', 'AI estimate'], ['gc_estimate', 'GC estimate'], ['average_of_bidders', 'Average of other bids'], ['median_of_bidders', 'Median of other bids'], ['min_of_bidders', 'Lowest of other bids'], ['max_of_bidders', 'Highest of other bids']]

export function RunProgress({ run }: { run: any }) {
  if (!run || run.status !== 'running') return null
  const p = run.total ? Math.min(1, run.done / run.total) : 0.15
  return (
    <div className="progress" role="status">
      <div className="row"><Sparkles size={16} color="#f79a5e" /><b>{run.step}</b><span className="spacer" /><span style={{ opacity: .7 }}>{run.total ? `${run.done} of ${run.total}` : ''}</span></div>
      {run.message && <div style={{ opacity: .7, fontSize: 12.5, marginTop: 2 }}>{run.message}</div>}
      <div className="bar"><i style={{ width: `${p * 100}%` }} /></div>
      <div className="steps">{(run.steps || []).map((s: string, i: number) => <i key={s} className={i < run.stepIndex ? 'done' : i === run.stepIndex ? 'now' : ''} title={s} />)}</div>
    </div>
  )
}

export default function Level() {
  const { pid } = useParams()
  const pkg = useResource(`/packages/${pid}`)
  const res = useResource(`/packages/${pid}/result`)
  const { run, watch } = useRun(pid, () => { res.reload(); pkg.reload() })
  const [sp] = useSearchParams()
  const [view, setView] = useState<'table' | 'landscape' | 'score'>((sp.get('view') as any) || 'table')
  const [sel, setSel] = useState<Sel>(() => {
    const c = sp.get('cell')?.split('.')
    return c?.length === 2 ? { type: 'cell', bidderId: c[0], key: c[1] } : sp.get('bidder') ? { type: 'bidder', id: sp.get('bidder')! } : sp.get('item') ? { type: 'item', key: sp.get('item')! } : null
  })
  const [q, setQ] = useState('')
  const [who, setWho] = useState('all')
  const [tint, setTint] = useState(true)
  const [menu, setMenu] = useState<{ x: number; y: number; bidderId: string; key: string } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const result = res.data
  const busy = run?.status === 'running'

  const level = useCallback(async (force = false) => watch(await post(`/packages/${pid}/level`, { forceExtract: force })), [pid, watch])
  const override = useCallback(async (bidderId: string, itemKey: string, body: any) => { setMenu(null); watch(await post(`/packages/${pid}/overrides`, { bidderId, itemKey, ...body })) }, [pid, watch])
  const addProposals = async (files: FileList | null) => {
    if (!files?.length) return
    for (const f of Array.from(files)) await upload(pid!, f, 'bid')
    level()
  }
  useEffect(() => { const close = () => setMenu(null); window.addEventListener('scroll', close, true); window.addEventListener('resize', close); return () => { window.removeEventListener('scroll', close, true); window.removeEventListener('resize', close) } }, [])
  useEffect(() => { const k = (e: KeyboardEvent) => { if (e.key === 'Escape') { setSel(null); setMenu(null) } }; window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k) }, [])

  const bidders = useMemo(() => !result ? [] : result.bidders.filter((b: any) => who === 'all' || (who === 'qualified' && b.qualified) || (who === 'top3' && b.rank && b.rank <= 3)), [result, who])
  const items = useMemo(() => new Set<string>(!result ? [] : result.items.filter((i: any) => !q || i.name.toLowerCase().includes(q.toLowerCase())).map((i: any) => i.key)), [result, q])
  const rec = result?.bidders.find((b: any) => b.id === result.recommendedId)
  const crumbs = [{ label: 'Projects', to: '/projects' }, { label: pkg.data?.project?.name || '…', picker: true }, { label: pkg.data?.code || '…', picker: true }, { label: 'Bid Level' }]
  const mcell = menu && result ? result.bidders.find((b: any) => b.id === menu.bidderId)?.cells[menu.key] : null

  return (
    <Shell pid={pid} crumbs={crumbs} flush>
      <div className="lvl-head">
        <div className="lvl-title">
          <h1 className="h-title">{pkg.data ? `${pkg.data.code} - ${pkg.data.name}` : ' '}</h1>
          {result && <span className="last"><Clock size={15} /> Last leveled {when(result.leveledAt)}</span>}
          <span className="spacer" />
          <a className="btn" href={result ? `/api/packages/${pid}/export.xlsx` : undefined} aria-disabled={!result} style={!result ? { opacity: .5, pointerEvents: 'none' } : undefined}><Upload size={16} /> Export</a>
          <button className="btn" onClick={() => fileRef.current?.click()} disabled={busy}><FileUp size={16} /> Add proposals</button>
          <input ref={fileRef} type="file" multiple hidden accept=".pdf,.docx,.xlsx,.xlsm" onChange={(e) => { addProposals(e.target.files); e.target.value = '' }} id="add-proposals" />
          <button className="btn primary" onClick={() => level(false)} disabled={busy}><Sparkles size={16} /> {result ? 'Level bids again' : 'Level bids'}</button>
        </div>
        {result && (
          <>
            <div className="lvl-sum">
              <span>{result.summary.leveled} of {result.summary.received} bids leveled</span>
              <span className="vr" />
              <span className="rec"><Sparkles size={16} /> Wyre AI recommends: <b>{rec ? rec.name : 'no bidder qualifies'}</b></span>
              <span className="vr" />
              <span className="sub">{result.summary.qualified} qualified{result.declined.length ? ` · ${result.declined.length} declined` : ''}{result.superseded.length ? ` · ${result.superseded.length} superseded` : ''}</span>
              <span className="spacer" />
              <div className="seg" role="tablist">
                <button className={view === 'table' ? 'on' : ''} onClick={() => setView('table')}><LayoutGrid size={15} /> Table</button>
                <button className={view === 'landscape' ? 'on' : ''} onClick={() => setView('landscape')}><MapIcon size={15} /> Landscape</button>
                <button className={view === 'score' ? 'on' : ''} onClick={() => setView('score')}><ListChecks size={15} /> Scorecard</button>
              </div>
              <label className="row input" style={{ gap: 8, width: 210 }}><Search size={15} className="muted" /><input style={{ border: 0, outline: 0, width: '100%' }} placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} id="item-search" /></label>
              <select className="select" value={who} onChange={(e) => setWho(e.target.value)} id="who" style={{ width: 190 }}>
                <option value="all">All subcontractors</option><option value="qualified">Qualified only</option><option value="top3">Wyre AI's top 3</option>
              </select>
            </div>
            {view === 'table' && (
              <div className="legend">
                <label className="switch" style={{ fontSize: 12.5 }}><input type="checkbox" checked={tint} onChange={(e) => setTint(e.target.checked)} id="tint" /><i />Colour by price position</label>
                <span className="k">Below median <span className="scale">{[0, 1, 2, 3, 4, 5, 6].map((i) => <i key={i} style={{ background: i === 3 ? '#fff' : `var(--c${i})` }} />)}</span> above</span>
                <span className="k"><span className="chip u">U</span> Unit normalized</span>
                <span className="k"><span className="chip q">Q</span> Quantity normalized</span>
                <span className="k"><span className="st plug" style={{ width: 18, height: 18 }}>+</span> Plugged <Sparkles size={12} color="var(--violet)" /> by AI</span>
                <span className="k"><i className="flagdot" /> To check</span>
                <span className="k"><span className="chip o">E</span> Estimator override</span>
                <span className="k" style={{ textDecoration: 'underline dashed', textUnderlineOffset: 4 }}>$0,000</span><span className="k">low-confidence reading</span>
              </div>
            )}
          </>
        )}
        {res.error && <div className="err">{res.error}</div>}
        {run?.status === 'error' && <div className="err" style={{ marginBottom: 14 }}>Leveling failed: {run.error}</div>}
      </div>

      {!result && !res.loading && !busy && (
        <div style={{ padding: '10px 52px' }}>
          <div className="empty">
            <Wand2 size={30} color="var(--violet)" />
            <h3>This package has not been leveled yet</h3>
            <p className="sub" style={{ maxWidth: 560 }}>{pkg.data?.scopeItems ? `${pkg.data.bids} proposals and ${pkg.data.scopeItems} baseline items are ready. Leveling reads every proposal, normalizes units and quantities, plugs the gaps, scores against the award policy and writes the explanations.` : 'Add baseline items first: open Scopes and generate them from the scope sheet.'}</p>
            {pkg.data?.scopeItems ? <button className="btn primary" onClick={() => level(false)}><Sparkles size={16} /> Level bids</button> : <Link className="btn primary" to={`/p/${pid}/scopes`}>Open Scopes</Link>}
          </div>
        </div>
      )}
      {result && view === 'table' && <BidTable result={result} bidders={bidders} items={items} tint={tint} sel={sel} onSel={setSel}
        onMenu={(e, bidderId, key) => { const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); setMenu({ x: Math.min(r.left, window.innerWidth - 250), y: Math.min(r.bottom + 4, window.innerHeight - 330), bidderId, key }) }}
        onAddItem={() => { window.location.href = `/p/${pid}/scopes` }} />}
      {result && view === 'landscape' && <Landscape result={result} bidders={bidders} sel={sel} onSel={setSel} />}
      {result && view === 'score' && <Scorecard result={result} bidders={bidders} onBidder={(id) => setSel({ type: 'bidder', id })} />}

      {menu && mcell && (
        <div className="menu" style={{ left: menu.x, top: menu.y }} onMouseLeave={() => setMenu(null)}>
          <button onClick={() => { setSel({ type: 'cell', bidderId: menu.bidderId, key: menu.key }); setMenu(null) }}>Open details and analysis</button>
          <hr />
          <div className="hd">Plug with</div>
          {PLUG_METHODS.map((m) => <button key={m[0]} onClick={() => override(menu.bidderId, menu.key, { action: 'plug', method: m[0] })}>{m[0] === 'ai_estimate' && <Sparkles size={14} color="var(--violet)" />}{m[1]}</button>)}
          <hr />
          <button onClick={() => override(menu.bidderId, menu.key, { action: 'include' })}>Mark as included</button>
          <button onClick={() => override(menu.bidderId, menu.key, { action: 'exclude' })}>Mark as not priced</button>
          {mcell.override && <button onClick={() => override(menu.bidderId, menu.key, { action: 'reset' })}>Remove override</button>}
        </div>
      )}
      {result && sel?.type === 'cell' && <CellPanel key={sel.bidderId + sel.key} result={result} bidderId={sel.bidderId} itemKey={sel.key} onClose={() => setSel(null)} busy={busy} onOverride={(b) => override(sel.bidderId, sel.key, b)} />}
      {result && sel?.type === 'bidder' && <BidderPanel result={result} id={sel.id} onClose={() => setSel(null)} />}
      {result && sel?.type === 'item' && <ItemPanel result={result} itemKey={sel.key} onClose={() => setSel(null)} onCell={(bidderId) => setSel({ type: 'cell', bidderId, key: sel.key })} />}
      <RunProgress run={run} />
    </Shell>
  )
}
