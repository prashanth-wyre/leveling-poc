import { NavLink, Link, useLocation, useNavigate } from 'react-router-dom'
import { Bell, ChevronLeft, ChevronRight, ChevronsUpDown, CircleHelp, ClockAlert, FileText, FolderClosed, History, BarChart3, Megaphone, PanelLeft, Scale, ShieldCheck, SlidersHorizontal, Sparkles, Target, Wrench } from 'lucide-react'
import type { ReactNode } from 'react'

function Logo({ size = 30 }: { size?: number }) {
  // a simple stacked-bars mark in the Wyre orange; not the registered logo artwork
  return (
    <svg width={size} height={size} viewBox="0 0 30 30" aria-hidden="true">
      <path d="M4 3 L11 7 V27 L4 23 Z" fill="#f2611d" />
      <path d="M13 9 L20 13 V17 L13 13 Z M13 15 L20 19 V23 L13 19 Z M13 21 L20 25 V27 H13 Z" fill="#f79a5e" />
      <path d="M22 15 h5 v2 h-5 Z M22 19 h5 v2 h-5 Z M22 23 h5 v2 h-5 Z" fill="#f2611d" />
    </svg>
  )
}

export type Crumb = { label: string; to?: string; picker?: boolean }

export function Shell({ pid, crumbs, children, flush }: { pid?: string; crumbs: Crumb[]; children: ReactNode; flush?: boolean }) {
  const nav = useNavigate()
  const loc = useLocation()
  const P = (page: string) => (pid ? `/p/${pid}/${page}` : '/projects')
  const items: { to?: string; label: string; icon: ReactNode; match?: string }[] = [
    { to: '/projects', label: 'Projects', icon: <FolderClosed size={18} />, match: '/projects' },
    { to: P('documents'), label: 'Documents', icon: <FileText size={18} />, match: '/documents' },
    { label: 'Ask Wyre', icon: <Sparkles size={18} /> },
    { to: P('scopes'), label: 'Scopes', icon: <Target size={18} />, match: '/scopes' },
    { to: P('policy'), label: 'Policy', icon: <Scale size={18} />, match: '/policy' },
    { label: 'Check', icon: <ClockAlert size={18} /> },
    { to: P('level'), label: 'Level', icon: <BarChart3 size={18} />, match: '/level' },
    { label: 'Project Admin', icon: <SlidersHorizontal size={18} /> },
    { label: 'Company Admin', icon: <Wrench size={18} /> },
    { label: 'Wyre AI Admin', icon: <ShieldCheck size={18} /> },
  ]
  return (
    <div className="shell">
      <nav className="rail" aria-label="Main">
        <Link to="/projects" className="logo" aria-label="Wyre AI home"><Logo size={34} /></Link>
        <button className="collapse" aria-label="Collapse menu" tabIndex={-1}><PanelLeft size={18} /></button>
        {items.map((it) =>
          it.to ? (
            <NavLink key={it.label} to={it.to} className={() => 'item' + (it.match && loc.pathname.endsWith(it.match) ? ' active' : '')}>
              <span className="ic">{it.icon}</span>{it.label}
            </NavLink>
          ) : (
            <span key={it.label} className="item" title="Not part of this build"><span className="ic">{it.icon}</span>{it.label}</span>
          ),
        )}
        <div className="me" title="Signed in">PR</div>
      </nav>
      <div className="main">
        <header className="topbar">
          <div className="crumbs">
            <span className="nav">
              <ChevronLeft size={16} style={{ cursor: 'pointer' }} onClick={() => nav(-1)} />
              <ChevronRight size={16} style={{ cursor: 'pointer' }} onClick={() => nav(1)} />
            </span>
            {crumbs.map((c, i) => (
              <span key={i} className="row" style={{ gap: 10 }}>
                {i > 0 && <span className="sep">/</span>}
                {c.to ? <Link to={c.to}>{c.label}</Link> : <span className={i === crumbs.length - 1 ? 'here' : ''}>{c.label}</span>}
                {c.picker && <ChevronsUpDown size={14} className="muted" />}
              </span>
            ))}
          </div>
          <div className="search"><Sparkles size={18} />Search your documents…</div>
          <div className="brand"><Logo size={26} />Wyre AI</div>
          <div className="icons"><History size={19} /><Bell size={19} /><Megaphone size={19} /><CircleHelp size={19} /></div>
        </header>
        <div className={'page' + (flush ? ' flush' : '')}>{children}</div>
      </div>
    </div>
  )
}
