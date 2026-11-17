import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ArrowDown, ArrowUp, Check, Save, Sparkles, X } from 'lucide-react'
import { Shell } from '../components/Shell'
import { post, put } from '../api'
import { useResource } from '../hooks'

const KIND: Record<string, string> = { price: 'Computed from leveled totals', scope_completeness: 'Computed from scope priced', qualitative: 'Rated by AI from the documents' }
const COLORS = ['#0b2a4a', '#1b62d1', '#5598e7', '#7c5cff', '#b7a6ff', '#9aa1ad', '#c9ced6']

export default function Policy() {
  const { pid } = useParams()
  const pkg = useResource(`/packages/${pid}`)
  const res = useResource(`/packages/${pid}/policy`)
  const [pol, setPol] = useState<any>(null)
  const [set, setSet] = useState<any>(null)
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState('')
  const [dirty, setDirty] = useState(false)
  useEffect(() => { if (res.data) { setPol(res.data.policy); setSet(res.data.settings); setDirty(false) } }, [res.data])
  const generate = async () => { setBusy('gen'); setMsg(''); try { const r = await post(`/packages/${pid}/policy/generate`); setPol(r.policy); setDirty(false); setMsg('Ordinals generated from the award policy. Level the package again to score with them.') } catch (e: any) { setMsg(e.message) } setBusy('') }
  const save = async () => {
    setBusy('save')
    try {
      if (pol) { const r = await put(`/packages/${pid}/policy`, { policy: pol }); setPol(r.policy) }
      const s = await put(`/packages/${pid}/settings`, set); setSet(s.settings); setDirty(false); setMsg('Saved. Level the package again to apply.')
    } catch (e: any) { setMsg(e.message) }
    setBusy('')
  }
  const crit: any[] = pol?.criteria || []
  const total = crit.reduce((a, c) => a + (+c.weight || 0), 0)
  const upd = (i: number, k: string, v: any) => { setPol({ ...pol, criteria: crit.map((c, j) => (j === i ? { ...c, [k]: v } : c)) }); setDirty(true) }
  const move = (i: number, d: number) => { const a = [...crit]; const j = i + d; if (j < 0 || j >= a.length) return;[a[i], a[j]] = [a[j], a[i]]; setPol({ ...pol, criteria: a.map((c, n) => ({ ...c, ordinal: n + 1 })) }); setDirty(true) }
  const S = (k: string, v: any) => { setSet({ ...set, [k]: v }); setDirty(true) }
  const D = (k: string, v: any) => { setSet({ ...set, default: { ...set.default, [k]: v } }); setDirty(true) }
  const methods: Record<string, string> = res.data?.methods || {}
  const award = pol?.award_rule || { basis: 'highest_score', best_value_window_pct: null, summary: '' }
  const setAward = (k: string, v: any) => {
    const a = { ...award, [k]: v }
    const w = a.best_value_window_pct
    a.summary = a.basis === 'lowest_price' ? `Lowest leveled total among qualified bidders${w ? `; a bidder within ${w}% of it may be chosen on weighted score` : ''}.` : 'Highest weighted score among qualified bidders.'
    setPol({ ...pol, award_rule: a }); setDirty(true)
  }
  return (
    <Shell pid={pid} crumbs={[{ label: 'Projects', to: '/projects' }, { label: pkg.data?.project?.name || '…' }, { label: pkg.data?.code || '…' }, { label: 'Policy' }]}>
      <div className="row wrap" style={{ marginBottom: 6 }}>
        <h1 className="h-title">Award policy</h1><span className="spacer" />
        <button className="btn" onClick={generate} disabled={!!busy}><Sparkles size={16} color="var(--violet)" /> {busy === 'gen' ? 'Reading the policy…' : pol ? 'Regenerate from policy' : 'Generate from policy'}</button>
        <button className="btn primary" onClick={save} disabled={!dirty || !!busy}><Save size={16} /> Save</button>
      </div>
      <p className="sub" style={{ marginBottom: 18, maxWidth: 900 }}>Wyre AI reads the award policy{res.data?.policyDocument ? <> (<b>{res.data.policyDocument}</b>)</> : ''} and turns it into ordinals: the evaluation criteria in order of importance, a weight for each, a rating scale, and the pass/fail rules. You can change the order and the weights; scoring always uses what is saved here.</p>
      {msg && <div className="pill ai" style={{ marginBottom: 14, padding: '6px 12px' }}>{msg}</div>}
      {!pol && !res.loading && <div className="empty"><Sparkles size={28} color="var(--violet)" /><h3>No ordinals yet</h3><p className="sub">They are generated the first time the package is leveled, or you can generate them now.</p><button className="btn primary" onClick={generate} disabled={!!busy}>{busy === 'gen' ? 'Reading…' : 'Generate from policy'}</button></div>}
      {pol && (
        <>
          <section className="card" style={{ marginBottom: 22, padding: '16px 20px' }}>
            <div className="row wrap"><b style={{ fontSize: 16 }}>Award rule</b><span className="pill ai"><Sparkles size={12} /> Read by AI from the policy</span>
              <span className="sub">Decides who is recommended among the bidders who pass the rules.</span></div>
            <p style={{ marginTop: 8 }}>{award.summary}</p>
            <div className="row wrap" style={{ marginTop: 10 }}>
              <select className="select" id="award-basis" value={award.basis} onChange={(e) => setAward('basis', e.target.value)}>
                <option value="lowest_price">Lowest leveled total among qualified bidders</option>
                <option value="highest_score">Highest weighted score among qualified bidders</option>
              </select>
              {award.basis === 'lowest_price' && <label className="row" style={{ gap: 8 }}><span className="sub">Best-value window</span>
                <input className="input" id="award-window" style={{ width: 80 }} type="number" min={0} step={0.5} value={award.best_value_window_pct ?? ''} placeholder="none"
                  onChange={(e) => setAward('best_value_window_pct', e.target.value === '' ? null : +e.target.value)} /><span className="sub">% above the lowest: within it, the best weighted score wins</span></label>}
            </div>
            {award.source_clause && <div className="clause">{award.source_clause}</div>}
          </section>
          <section className="card" style={{ marginBottom: 22 }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--line)' }}>
              <div className="row wrap"><b style={{ fontSize: 16 }}>Ordinals and weights</b><span className={'pill ' + (pol.source === 'ai' ? 'ai' : '')}>{pol.source === 'ai' ? 'Generated by AI' : pol.source === 'edited' ? 'Edited' : 'Default'}</span><span className="spacer" />
                <span className={'pill ' + (Math.abs(total - 100) < 0.05 ? 'green' : 'amber')}>Weights total {total.toFixed(1)}%{Math.abs(total - 100) < 0.05 ? '' : ' · rescaled to 100 on save'}</span></div>
              <p className="sub" style={{ marginTop: 6 }}>{pol.summary}</p>
              <div className="weightbar" style={{ marginTop: 12 }}>{crit.map((c, i) => <i key={c.id} style={{ width: `${(c.weight / (total || 1)) * 100}%`, background: COLORS[i % COLORS.length] }} title={`${c.name}: ${c.weight}%`} />)}</div>
            </div>
            {crit.map((c, i) => (
              <div className="crit" key={c.id}>
                <div><div className="ord" style={{ background: COLORS[i % COLORS.length] }}>{i + 1}</div>
                  <div className="row" style={{ gap: 2, marginTop: 8 }}><button className="btn small ghost" style={{ padding: 4 }} aria-label="Move up" onClick={() => move(i, -1)}><ArrowUp size={14} /></button><button className="btn small ghost" style={{ padding: 4 }} aria-label="Move down" onClick={() => move(i, 1)}><ArrowDown size={14} /></button></div></div>
                <div style={{ minWidth: 0 }}>
                  <div className="row wrap"><b style={{ fontSize: 15.5 }}>{c.name}</b><span className="pill">{KIND[c.kind]}</span></div>
                  <p className="sub" style={{ marginTop: 4 }}>{c.description}</p>
                  <p style={{ marginTop: 6, fontSize: 13 }}><b>How it is scored:</b> {c.how_scored}</p>
                  <div className="scale">{(c.scale || []).map((s: any) => <div className="lv" key={s.level}><b>{s.label} · {s.points} pts</b><span className="sub">{s.definition}</span></div>)}</div>
                  {c.source_clause && <div className="clause">{c.source_clause}</div>}
                  {c.rationale && <p className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>Why this weight: {c.rationale}</p>}
                </div>
                <div className="wbox">
                  <span className="lab">Weight</span>
                  <div className="w"><input className="input" type="number" min={0} max={100} step={1} value={c.weight} onChange={(e) => upd(i, 'weight', +e.target.value)} aria-label={`Weight for ${c.name}`} id={'w-' + c.id} /><b>%</b></div>
                  <input type="range" min={0} max={100} step={1} value={c.weight} onChange={(e) => upd(i, 'weight', +e.target.value)} aria-label={`Weight slider for ${c.name}`} />
                </div>
              </div>
            ))}
          </section>
          <section className="card" style={{ marginBottom: 22 }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--line)' }}><b style={{ fontSize: 16 }}>Pass / fail rules</b> <span className="sub">{pol.gates.length} read from the policy. A bidder that fails a disqualifying rule is not ranked.</span></div>
            <table className="plain"><thead><tr><th>Rule</th><th>How it is checked</th><th>If failed</th><th>Policy clause</th></tr></thead>
              <tbody>{pol.gates.map((g: any, i: number) => (
                <tr key={g.id}><td style={{ maxWidth: 420 }}><b>{g.name}</b><div className="sub" style={{ fontSize: 13 }}>{g.rule}</div></td>
                  <td>{g.check === 'scope_priced_min_pct' ? `Computed: at least ${g.threshold}% of scope priced` : g.check === 'bid_validity_min_days' ? `Computed: valid ${g.threshold} days or more` : 'Judged by AI from the documents'}</td>
                  <td><select className="select small" value={g.severity} id={'sev-' + g.id} onChange={(e) => { setPol({ ...pol, gates: pol.gates.map((x: any, j: number) => (j === i ? { ...x, severity: e.target.value } : x)) }); setDirty(true) }}><option value="disqualify">Disqualify</option><option value="flag">Flag only</option></select></td>
                  <td className="sub" style={{ fontSize: 12.5, maxWidth: 320, fontStyle: 'italic' }}>{g.source_clause}</td></tr>))}
                {!pol.gates.length && <tr><td colSpan={4} className="muted">No mandatory rules.</td></tr>}</tbody></table>
          </section>
        </>
      )}
      {set && (
        <section className="card">
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--line)' }}><b style={{ fontSize: 16 }}>Normalization and plugs</b></div>
          <div style={{ padding: 20, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 22 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <label className="switch"><input type="checkbox" checked={!!set.ai_auto} onChange={(e) => S('ai_auto', e.target.checked)} id="ai-auto" /><i />Auto-estimate plugs with AI</label>
              <p className="sub" style={{ fontSize: 13, marginTop: -6 }}>When on, every gap is first plugged with the model's estimate of the unit cost, converted to the GC unit. The policy method below is the fallback.</p>
              <label className="switch"><input type="checkbox" checked={!!set.ai_web_search} onChange={(e) => S('ai_web_search', e.target.checked)} id="ai-web" /><i />Let AI estimates use web search</label>
              <label className="switch"><input type="checkbox" checked={set.ai_text !== false} onChange={(e) => S('ai_text', e.target.checked)} id="ai-text" /><i />AI-written explanations</label>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <label className="lab" htmlFor="thr">Quantity threshold</label>
              <div className="row"><input className="input" id="thr" style={{ width: 90 }} type="number" min={0} step={0.5} value={set.threshold_pct} onChange={(e) => S('threshold_pct', +e.target.value)} /><span className="sub">% difference from the GC takeoff before a bid is re-extended at the GC quantity</span></div>
              <label className="lab" htmlFor="dm">Default plug method</label>
              <select className="select" id="dm" value={set.default.method} onChange={(e) => D('method', e.target.value)}>{Object.entries(methods).filter(([k]) => !['manual', 'fixed_allowance'].includes(k)).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
              <span className="sub" style={{ fontSize: 13 }}>Falls back to: {(set.default.fallback || []).map((f: any) => methods[typeof f === 'string' ? f : f.method]).join(', ') || 'nothing'}. Needs {set.default.min_pool} comparable prices; outliers beyond {set.default.outlier_trim_pct}% of the median are left out.</span>
            </div>
            <div>
              <span className="lab">Per-item methods and allowances</span>
              <table className="plain" style={{ fontSize: 13, marginTop: 6 }}><tbody>
                {Object.entries<any>(set.items || {}).map(([k, r]) => <tr key={k}><td>{res.data.items.find((i: any) => i.key === k)?.name || k}</td><td>{methods[r.method] || r.method}{r.amount ? ` $${(+r.amount).toLocaleString()}` : ''}{r.rate_source ? ` (${r.rate_source})` : ''}</td></tr>)}
                {(set.allowances || []).map((a: any) => <tr key={a.name}><td>Allowance, all bidders: {a.name}</td><td>${(+a.amount).toLocaleString()}</td></tr>)}
                {!Object.keys(set.items || {}).length && !(set.allowances || []).length && <tr><td className="muted">Every item uses the default method.</td></tr>}
              </tbody></table>
            </div>
          </div>
        </section>
      )}
    </Shell>
  )
}
