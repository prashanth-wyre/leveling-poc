import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'

type TipApi = { show: (e: { clientX: number; clientY: number }, content: ReactNode) => void; hide: () => void }
const Ctx = createContext<TipApi>({ show: () => {}, hide: () => {} })
export const useTip = () => useContext(Ctx)

/** One floating tooltip for the whole app, positioned at the pointer and kept on screen. */
export function TipProvider({ children }: { children: ReactNode }) {
  const [tip, setTip] = useState<{ x: number; y: number; content: ReactNode } | null>(null)
  const ref = useRef<HTMLDivElement>(null)
  const show = useCallback((e: { clientX: number; clientY: number }, content: ReactNode) => setTip({ x: e.clientX, y: e.clientY, content }), [])
  const hide = useCallback(() => setTip(null), [])
  const value = useMemo(() => ({ show, hide }), [show, hide])
  let style: any = { left: -9999, top: -9999 }
  if (tip) {
    const w = ref.current?.offsetWidth || 300, h = ref.current?.offsetHeight || 80, pad = 14
    let x = tip.x + pad, y = tip.y + pad
    if (x + w > window.innerWidth - 8) x = tip.x - w - pad
    if (y + h > window.innerHeight - 8) y = tip.y - h - pad
    style = { left: Math.max(8, x), top: Math.max(8, y) }
  }
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="tip" ref={ref} style={style} hidden={!tip}>{tip?.content}</div>
    </Ctx.Provider>
  )
}
