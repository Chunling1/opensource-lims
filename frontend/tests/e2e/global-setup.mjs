import { createServer } from 'vite'

export default async function setup() {
  const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173'
  if (!process.env.CI) {
    try {
      const response = await fetch(baseURL, { signal: AbortSignal.timeout(1500) })
      if (response.ok && (await response.text()).includes('LIMS')) return
    } catch { /* Start an owned server below. */ }
  }
  // Owned regression servers skip demo latency unless a timing test explicitly requests it.
  process.env.LIMS_MOCK_QUERY_DELAY_MS ??= '0'
  await import('../../scripts/prepare-assets.mjs')
  // Own Vite directly, so Windows teardown does not depend on killing npm's
  // shell/process tree. Playwright invokes the returned cleanup after all tests.
  const server = await createServer({ server: { host: '127.0.0.1', port: Number(new URL(baseURL).port), strictPort: true } })
  await server.listen()
  return async () => { await server.close() }
}
