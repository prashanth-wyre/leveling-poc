import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Plus, Save, Sparkles, Trash2 } from 'lucide-react'
import { Shell } from '../components/Shell'
import { post, put } from '../api'
import { useResource } from '../hooks'
import { money } from '../format'

export default function Scopes() {
  const { pid } = useParams()
  const pkg = useResource(`/packages/${pid}`)
  const scope = useResource(`/packages/${pid}/scope`)
  const [items, setItems] = useState<any[]>([])
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState('')
  useEffect(() => { if (scope.data) { setItems(scope.data.items || []); setDirty(false) } }, [scope.data])
  const set = (i: number, k: string, v: any) => { setItems(items.map((it, j) => (j === i ? { ...it, [k]: v } : it))); setDirty(true) }
  const save = async () => { setBusy('save'); try { const r = await put(`/packages/${pid}/scope`, { items }); setItems(r.items); setDirty(false); setMsg('Saved. Level the package again to apply the change.') } catch (e: any) { setMsg(e.message) } setBusy('') }
  const generate = async () => { setBusy('gen'); setMsg(''); try { const r = await post(`/packages/${pid}/scope/generate`); setItems(r.items); setDirty(false); setMsg(`${r.items.length} baseline items read from ${r.source}.`) } catch (e: any) { setMsg(e.message) } setBusy('') }
  const total = items.reduce((a, it) => a + (+it.estimate || 0), 0)
  return (
    <Shell pid={pid} crumbs={[{ label: 'Projects', to: '/projects' }, { label: pkg.data?.project?.name || '…' }, { label: pkg.data?.code || '…' }, { label: 'Scopes' }]}>
      <div className="row wrap" style={{ marginBottom: 6 }}>
        <h1 className="h-title">Baseline items</h1><span className="spacer" />
        <button className="btn" onClick={generate} disabled={!!busy}><Sparkles size={16} color="var(--violet)" /> {busy === 'gen' ? 'Reading the scope sheet…' : 'Generate from scope sheet'}</button>
        <button className="btn" onClick={() => { setItems([...items, { key: `ITEM${items.length + 1}`, name: '', section: items[items.length - 1]?.section || 'General', unit: 'LS', qty: null, rate: null, estimate: null, depth: null }]); setDirty(true) }}><Plus size={16} /> Add item</button>
        <button className="btn primary" onClick={save} disabled={!dirty || !!busy}><Save size={16} /> Save</button>
      </div>
      <p className="sub" style={{ marginBottom: 18 }}>The scope items every proposal is leveled against, with the GC's takeoff quantity, unit and estimate. Quantities and units here are what bids are normalized to. {items.length} items, GC estimate {money(total)}.</p>
      {msg && <div className="pill ai" style={{ marginBottom: 14, padding: '6px 12px' }}>{msg}</div>}
      {!items.length && !scope.loading && <div className="empty"><Sparkles size={28} color="var(--violet)" /><h3>No baseline items yet</h3><p className="sub">Let Wyre AI read them from the uploaded scope sheet, or add them by hand.</p><button className="btn primary" onClick={generate} disabled={!!busy}>{busy === 'gen' ? 'Reading…' : 'Generate from scope sheet'}</button></div>}
      {items.length > 0 && (
        <div className="card" style={{ overflowX: 'auto' }}>
          <table className="plain">
            <thead><tr><th>Key</th><th style={{ minWidth: 300 }}>Scope item</th><th>Section</th><th>Unit</th><th className="num">GC quantity</th><th className="num">Unit rate</th><th className="num">GC estimate</th><th className="num">Depth (in.)</th><th /></tr></thead>
            <tbody>{items.map((it, i) => (
              <tr key={i}>
                <td><input className="input small" style={{ width: 96 }} value={it.key || ''} onChange={(e) => set(i, 'key', e.target.value.toUpperCase())} aria-label="Key" /></td>
                <td><input className="input small" style={{ width: '100%' }} value={it.name || ''} onChange={(e) => set(i, 'name', e.target.value)} aria-label="Scope item" /></td>
                <td><input className="input small" style={{ width: 190 }} value={it.section || ''} onChange={(e) => set(i, 'section', e.target.value)} aria-label="Section" /></td>
                <td><input className="input small" style={{ width: 62 }} value={it.unit || ''} onChange={(e) => set(i, 'unit', e.target.value.toUpperCase())} aria-label="Unit" /></td>
                {(['qty', 'rate', 'estimate', 'depth'] as const).map((k) => <td key={k} className="num"><input className="input small" style={{ width: k === 'depth' ? 64 : 104, textAlign: 'right' }} value={it[k] ?? ''} inputMode="decimal" onChange={(e) => set(i, k, e.target.value === '' ? null : e.target.value)} aria-label={k} /></td>)}
                <td><button className="btn small ghost" aria-label="Remove" onClick={() => { setItems(items.filter((_, j) => j !== i)); setDirty(true) }}><Trash2 size={14} /></button></td>
              </tr>))}</tbody>
          </table>
        </div>
      )}
    </Shell>
  )
}
