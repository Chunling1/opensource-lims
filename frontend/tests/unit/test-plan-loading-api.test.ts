import { createServer } from 'node:http'
import { expect, it } from 'vitest'
import { createRegistrationMiddleware } from '../../server/registrationApi'

it('applies the shared demo delay to plan queries and checkbox updates', async () => {
  const middleware = createRegistrationMiddleware()
  const server = createServer((req, res) => middleware(req, res, () => { res.writeHead(404); res.end() }))
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${(server.address() as { port: number }).port}/api/registration`
  try {
    const session = await fetch(base + '/session', { method: 'POST' })
    const cookie = session.headers.get('set-cookie')!.split(';')[0]!
    const call = async (path: string, body: object) => {
      const started = performance.now()
      const response = await fetch(base + path, { method: 'POST', headers: { cookie, 'X-Demo-Actor': 'admin', 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      expect(response.status).toBe(200)
      expect(performance.now() - started).toBeGreaterThanOrEqual(1900)
      return response.json()
    }
    const [query, selected] = await Promise.all([
      call('/test-plans/query', { parentId: 'pressure' }),
      call('/test-plans/selection', { selection: { groupIds: [], planIds: [], excludedPlanIds: [] }, toggle: { kind: 'plan', id: 'pressure-1', checked: true } }),
    ])
    expect(query.items.map((row: { id: string }) => row.id)).toContain('pressure-1')
    expect(selected).toMatchObject({ count: 1, selection: { planIds: ['pressure-1'] } })
  } finally {
    middleware.dispose()
    await new Promise<void>(resolve => server.close(() => resolve()))
  }
}, 15000)
