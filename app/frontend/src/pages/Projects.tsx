import { Link } from 'react-router-dom'
import { ChevronRight, FolderClosed, Sparkles } from 'lucide-react'
import { Shell } from '../components/Shell'
import { useResource } from '../hooks'
import { money, when } from '../format'

export default function Projects() {
  const { data, error } = useResource<any[]>('/projects')
  return (
    <Shell crumbs={[{ label: 'Projects' }]}>
      <h1 className="h-title">Projects</h1>
      <p className="sub" style={{ marginTop: 6, marginBottom: 26 }}>Pick a bid package to level. Each package has its proposals, baseline items and award policy.</p>
      {error && <div className="err">{error}</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
        {(data || []).map((p) => (
          <section className="card" key={p.id}>
            <div className="row" style={{ padding: '16px 20px', borderBottom: '1px solid var(--line)' }}>
              <FolderClosed size={18} color="var(--navy)" /><b style={{ fontSize: 16 }}>{p.name}</b><span className="sub">{p.location}</span>
            </div>
            <table className="plain">
              <thead><tr><th>Bid package</th><th className="num">Proposals</th><th className="num">Baseline items</th><th>Status</th><th>Wyre AI recommends</th><th /></tr></thead>
              <tbody>{p.packages.map((k: any) => (
                <tr key={k.id}>
                  <td><Link to={`/p/${k.id}/level`} style={{ color: 'var(--ink)', fontWeight: 600 }}>{k.code} - {k.name}</Link></td>
                  <td className="num">{k.bids}</td>
                  <td className="num">{k.scopeItems || <span className="pill amber">none yet</span>}</td>
                  <td>{k.run?.status === 'running' ? <span className="pill ai"><Sparkles size={12} /> Leveling…</span> : k.lastLeveledAt ? <span className="pill green">Leveled {when(k.lastLeveledAt)}</span> : <span className="pill">Not leveled</span>}</td>
                  <td>{k.recommended ? <span><b>{k.recommended}</b> <span className="sub">{money(k.recommendedTotal)}</span></span> : <span className="muted">–</span>}</td>
                  <td className="num"><Link className="btn small" to={`/p/${k.id}/level`}>Open <ChevronRight size={14} /></Link></td>
                </tr>))}</tbody>
            </table>
          </section>
        ))}
      </div>
    </Shell>
  )
}
