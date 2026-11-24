export type TransferProgress = (loaded: number, total: number) => void
export function uploadRequest(url: string, method: string, body: string, actorId: string, progress: TransferProgress, signal?: AbortSignal): Promise<Response> {
  return new Promise((resolve, reject) => {
    signal?.throwIfAborted()
    const xhr = new XMLHttpRequest()
    const abort = () => xhr.abort()
    const cleanup = () => signal?.removeEventListener('abort', abort)
    xhr.open(method, url)
    xhr.setRequestHeader('Content-Type', 'application/json')
    xhr.setRequestHeader('X-Demo-Actor', actorId)
    xhr.upload.onprogress = event => { if (event.lengthComputable) progress(event.loaded, event.total) }
    xhr.onload = () => {
      cleanup()
      const headers = new Headers()
      for (const line of xhr.getAllResponseHeaders().trim().split(/[\r\n]+/)) { const index = line.indexOf(':'); if (index > 0) headers.append(line.slice(0, index), line.slice(index + 1).trim()) }
      resolve(new Response(xhr.responseText, { status: xhr.status, headers }))
    }
    xhr.onerror = () => { cleanup(); reject(new Error('上传连接失败')) }
    xhr.onabort = () => { cleanup(); reject(new DOMException('已取消上传', 'AbortError')) }
    signal?.addEventListener('abort', abort, { once: true })
    xhr.send(body)
  })
}
