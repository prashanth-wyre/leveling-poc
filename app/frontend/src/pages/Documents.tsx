import { useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertTriangle, ExternalLink, FileText, Sparkles, Trash2, Upload, X } from 'lucide-react'
import { Shell } from '../components/Shell'
import { del, patch, post, upload } from '../api'
import { useResource, useRun } from '../hooks'
import { KIND, day, money, num, when } from '../format'
import { RunProgress } from './Level'

const STATUS: Record<string, [string, string]> = { uploaded: ['Not read yet', ''], extracted: ['Read by AI', 'green'], declined: ['Decline notice', 'amber'], not_a_bid: ['Not a bid', 'amber'], error: ['Could not be read', 'red'] }

function Extraction({ id, scope, onClose }: { id: string; scope: any; onClose: () => void }) {
  const { data } = useResource(`/documents/${id}`)
  const ext = data?.extraction
  const name = (k: string) => scope?.items?.find((i: any) => i.key === k)?.name || k
  return (
    <aside className="drawer" style={{ width: 760 }} aria-label="What the AI read">
      <div className="dh">
        <div><div className="lab" style={{ marginBottom: 4 }}>What the AI read</div><h3>{data?.filename}</h3>
          {ext && <div className="row wrap" style={{ marginTop: 8, gap: 6 }}><span className="pill ai"><Sparkles size={12} /> {ext.bidder_name}</span>{ext.bid_date && <span className="pill">{ext.bid_date}</span>}
            {ext.stated_total != null && <span className="pill">Stated total {money(ext.stated_total, 2)}</span>}<span className="pill">Lines read {money(ext.lines_total, 2)}</span>{ext.is_revision && <span className="pill amber">Revision</span>}</div>}</div>
        <button className="btn small x" onClick={onClose} aria-label="Close"><X size={15} /></button>
      </div>
      <div className="db">
        {!ext && <p className="muted">{data ? 'This document has not been read yet. Level the package to read it.' : 'Loading…'}</p>}
        {ext?.checks?.length > 0 && <div className="checks">{ext.checks.map((c: string, i: number) => <div className="c" key={i}><AlertTriangle size={15} style={{ flex: 'none' }} />{c}</div>)}</div>}
        {ext && <div><h4>Baseline items</h4>
          <table className="plain" style={{ fontSize: 12.5 }}><thead><tr><th>Item</th><th>Status</th><th className="num">Qty</th><th>Unit</th><th className="num">Unit price</th><th className="num">Amount</th><th className="num">Conf.</th></tr></thead>
            <tbody>{Object.values<any>(ext.cells).map((c) => (
              <tr key={c.scope_key}><td><b>{name(c.scope_key)}</b>{c.source_snippet && <div className="muted" style={{ fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 11.5, marginTop: 2 }}>{c.source_snippet}</div>}
                {c.gc_units_per_bid_unit && <div style={{ color: 'var(--blue)', marginTop: 2 }}>Conversion: {c.conversion_explanation || `x${c.gc_units_per_bid_unit}`}</div>}{c.note && <div className="sub">{c.note}</div>}</td>
                <td><span className={'pill ' + (c.status === 'priced' ? 'green' : c.status === 'excluded' ? 'red' : c.status === 'included' ? '' : 'amber')}>{c.status.replace('_', ' ')}</span></td>
                <td className="num">{num(c.quantity)}</td><td>{c.unit}</td><td className="num">{c.unit_price != null ? money(c.unit_price, 2) : ''}</td><td className="num">{c.amount != null ? money(c.amount, 2) : ''}</td>
                <td className="num" style={{ color: c.confidence < 0.7 ? 'var(--red)' : undefined }}>{Math.round(c.confidence * 100)}%</td></tr>))}</tbody></table></div>}
        {ext?.extra_lines?.length > 0 && <div><h4>Other priced lines</h4><table className="plain" style={{ fontSize: 12.5 }}><tbody>{ext.extra_lines.map((e: any, i: number) => <tr key={i}><td>{e.description}</td><td><span className="pill">{e.treatment}</span></td><td className="num">{money(e.amount, 2)}</td></tr>)}</tbody></table></div>}
        {ext && ['warranty', 'exclusions', 'inclusions', 'clarifications', 'red_flags'].map((k) => ext[k]?.length ? <div key={k}><h4>{k.replace('_', ' ')}</h4><ul style={{ margin: 0, paddingLeft: 18, color: 'var(--ink-2)' }}>{ext[k].map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></div> : null)}
        {data?.hasFile && <a className="row" style={{ gap: 6 }} href={`/api/documents/${id}/file`} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Open the original file</a>}
      </div>
    </aside>
  )
}

export default function Documents() {
  const { pid } = useParams()
  const pkg = useResource(`/packages/${pid}`)
  const docs = useResource<any[]>(`/packages/${pid}/documents`)
  const scope = useResource(`/packages/${pid}/scope`)
  const { run, watch } = useRun(pid, () => docs.reload())
  const [open, setOpen] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const ref = useRef<HTMLInputElement>(null)
  const add = async (files: FileList | null) => {
    if (!files?.length) return
    setBusy(true)
    for (const f of Array.from(files)) await upload(pid!, f)
    setBusy(false)
    docs.reload()
  }
  const groups = ['bid', 'award_policy', 'scope_sheet', 'plug_policy', 'supporting']
  return (
    <Shell pid={pid} crumbs={[{ label: 'Projects', to: '/projects' }, { label: pkg.data?.project?.name || '…' }, { label: pkg.data?.code || '…' }, { label: 'Documents' }]}>
      <div className="row wrap" style={{ marginBottom: 6 }}>
        <h1 className="h-title">Documents</h1><span className="spacer" />
        <button className="btn" onClick={() => ref.current?.click()} disabled={busy}><Upload size={16} /> Upload</button>
        <input ref={ref} type="file" multiple hidden onChange={(e) => { add(e.target.files); e.target.value = '' }} id="doc-upload" />
        <button className="btn primary" onClick={async () => watch(await post(`/packages/${pid}/level`, {}))} disabled={run?.status === 'running'}><Sparkles size={16} /> Read and level</button>
      </div>
      <p className="sub" style={{ marginBottom: 22 }}>Proposals in PDF, Word or Excel are read by AI against the baseline items. The award policy becomes the scoring ordinals. Supporting documents are used when judging pass/fail rules.</p>
      <div style={{ border: '1.5px dashed var(--line)', borderRadius: 12, padding: 22, textAlign: 'center', color: 'var(--ink-2)', marginBottom: 24 }}
        onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); add(e.dataTransfer.files) }}>
        Drop files here, or use Upload. The type is guessed from the file name and can be changed below.
      </div>
      {groups.map((g) => {
        const list = (docs.data || []).filter((d) => d.kind === g)
        if (!list.length) return null
        return (
          <section className="card" key={g} style={{ marginBottom: 20, overflowX: 'auto' }}>
            <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--line)' }}><b>{KIND[g]}{g === 'bid' ? 's' : ''}</b> <span className="sub">{list.length}</span></div>
            <table className="plain"><thead><tr><th>File</th><th>Type</th><th>Status</th>{g === 'bid' && <><th>Bidder</th><th>Bid date</th><th className="num">Total read</th><th>Checks</th></>}<th>Uploaded</th><th /></tr></thead>
              <tbody>{list.map((d) => (
                <tr key={d.id}>
                  <td><a className="row" style={{ gap: 8, color: 'var(--ink)', cursor: 'pointer', fontWeight: 600 }} onClick={() => (g === 'bid' ? setOpen(d.id) : d.hasFile && window.open(`/api/documents/${d.id}/file`))}><FileText size={15} className="muted" />{d.filename}</a></td>
                  <td><select className="select small" value={d.kind} id={'kind-' + d.id} onChange={async (e) => { await patch(`/documents/${d.id}`, { kind: e.target.value }); docs.reload() }}>{Object.entries(KIND).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></td>
                  <td>{g === 'bid' ? <span className={'pill ' + (STATUS[d.status]?.[1] || '')} title={d.error || ''}>{STATUS[d.status]?.[0] || d.status}</span> : <span className="pill">Stored</span>}</td>
                  {g === 'bid' && <><td>{d.bidder}{d.isRevision && <span className="pill amber" style={{ marginLeft: 6 }}>revision</span>}</td><td>{day(d.bidDate)}</td>
                    <td className="num">{d.statedTotal != null ? money(d.statedTotal, 2) : d.linesTotal ? money(d.linesTotal, 2) : ''}</td>
                    <td>{d.checks.length ? <span className="pill amber" title={d.checks.join('\n')}><AlertTriangle size={12} /> {d.checks.length}</span> : ''}</td></>}
                  <td className="sub">{when(d.uploadedAt)}</td>
                  <td className="num"><button className="btn small ghost" aria-label="Delete" onClick={async () => { await del(`/documents/${d.id}`); docs.reload() }}><Trash2 size={14} /></button></td>
                </tr>))}</tbody></table>
          </section>
        )
      })}
      {open && <Extraction id={open} scope={scope.data} onClose={() => setOpen(null)} />}
      <RunProgress run={run} />
    </Shell>
  )
}
