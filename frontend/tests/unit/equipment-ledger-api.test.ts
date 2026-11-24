import { createServer } from 'node:http'
import { expect, it } from 'vitest'
import { createRegistrationMiddleware } from '../../server/registrationApi'

it('serves equipment queries with the shared delay, scoped exports and business validation', async () => {
  const middleware = createRegistrationMiddleware()
  const server = createServer((req, res) => middleware(req, res, () => { res.writeHead(404); res.end() }))
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${(server.address() as { port: number }).port}/api/registration`
  try {
    const session = await fetch(base + '/session', { method: 'POST' }), cookie = session.headers.get('set-cookie')!.split(';')[0]!
    const call = (operation: string, data: unknown, actor = 'admin') => fetch(base + '/quality/equipment/ledger/' + operation, { method: 'POST', headers: { cookie, 'X-Demo-Actor': actor, 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
    const started = performance.now(), result = await call('query', {})
    expect(performance.now() - started).toBeGreaterThanOrEqual(1900)
    expect(result.status).toBe(200)
    expect(await result.json()).toMatchObject({ total: 24, page: 1, pageSize: 10 })
    const csv = await call('export', { code: 'DEMO-001' })
    expect(csv.headers.get('content-type')).toContain('text/csv')
    const text = await csv.text(); expect(text).toContain('DEMO-001'); expect(text).not.toContain('DEMO-002')
    expect((await call('query', { from: '2026-02-30' })).status).toBe(422)
    expect((await call('query', {}, 'analyst')).status).toBe(403)
    expect((await call('delete', {})).status).toBe(404)
  } finally { middleware.dispose(); await new Promise<void>(resolve => server.close(() => resolve())) }
}, 20000)

it('forces department scope for the department ledger query and export', async () => {
  const middleware = createRegistrationMiddleware({ queryDelayMs: 0 })
  const server = createServer((req, res) => middleware(req, res, () => { res.writeHead(404); res.end() }))
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${(server.address() as { port: number }).port}/api/registration`
  try {
    const session = await fetch(base + '/session', { method: 'POST' }), cookie = session.headers.get('set-cookie')!.split(';')[0]!
    const call = (path: string, data: unknown) => fetch(base + '/quality/equipment/' + path, { method: 'POST', headers: { cookie, 'X-Demo-Actor': 'admin', 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
    const all = await (await call('ledger/query', { pageSize: 50 })).json()
    const expected = all.items.filter((row: { departmentId: string }) => row.departmentId === 'lab')
    const response = await call('department-ledger/query', { ownDepartment: false, pageSize: 50 })
    expect(response.status).toBe(200)
    expect((await response.json()).items).toEqual(expected)
    expect((await (await call('department-ledger/query', { departmentId: 'lab2', ownDepartment: false })).json()).total).toBe(0)
    expect((await (await call('department-ledger/query', { unassociated: true })).json()).total).toBe(0)
    const csv = await (await call('department-ledger/export', { ownDepartment: false })).text()
    for (const row of all.items) expect(csv.includes(`"${row.code}"`)).toBe(row.departmentId === 'lab')
    for (const action of ['save', 'batch-update', 'import', 'template', 'delete']) expect((await call('department-ledger/' + action, {})).status).toBe(404)
  } finally { middleware.dispose(); await new Promise<void>(resolve => server.close(() => resolve())) }
})
