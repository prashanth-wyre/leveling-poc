export const money = (v: number | null | undefined, dec = 0) =>
  v == null ? '–' : (v < 0 ? '-' : '') + '$' + Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
export const signed = (v: number) => (v > 0 ? '+' : v < 0 ? '-' : '') + '$' + Math.abs(Math.round(v)).toLocaleString('en-US')
export const short = (v: number) => {
  const a = Math.abs(v)
  return (v < 0 ? '-' : '') + '$' + (a >= 1e6 ? (a / 1e6).toFixed(2) + 'M' : a >= 1e4 ? Math.round(a / 1e3) + 'k' : a >= 1e3 ? (a / 1e3).toFixed(1) + 'k' : Math.round(a))
}
export const pct = (d: number, dec = 0) => (d >= 0 ? '+' : '') + (d * 100).toFixed(dec) + '%'
export const num = (v: number | null | undefined) => (v == null ? '–' : v.toLocaleString('en-US', { maximumFractionDigits: 2 }))
export const when = (t?: number | null) =>
  t ? new Date(t * 1000).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true }).replace(',', '').replace(' am', ' AM').replace(' pm', ' PM') : ''
export const day = (iso?: string | null) => {
  if (!iso) return ''
  const d = new Date(iso + 'T00:00:00')
  return isNaN(+d) ? iso : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
export const KIND: Record<string, string> = { bid: 'Proposal', award_policy: 'Award policy', plug_policy: 'Plugging policy', scope_sheet: 'Scope sheet', supporting: 'Supporting' }
export const BAND: Record<string, string> = { recommended: 'Recommended', alternative: 'Alternative', other: 'Not in top 3', not_qualified: 'Did not qualify' }
