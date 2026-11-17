// Thin fetch helpers. Errors carry the server's message so pages can show it.
export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch('/api' + path, opts)
  if (!res.ok) {
    let msg = res.statusText
    try { msg = (await res.json()).detail || msg } catch { /* not json */ }
    const err: any = new Error(msg)
    err.status = res.status
    throw err
  }
  return res.json()
}
const json = (method: string) => (path: string, body?: any) =>
  api(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}) })
export const post = json('POST')
export const put = json('PUT')
export const patch = json('PATCH')
export const del = (path: string) => api(path, { method: 'DELETE' })
export async function upload(pid: string, file: File, kind = '') {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('kind', kind)
  return api(`/packages/${pid}/documents`, { method: 'POST', body: fd })
}
