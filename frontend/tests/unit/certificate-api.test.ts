import { randomUUID } from 'node:crypto'
import { createServer } from 'node:http'
import { afterAll, beforeAll, expect, it } from 'vitest'
import { createRegistrationMiddleware } from '../../server/registrationApi'

async function start(delay?: number) {
  const middleware = createRegistrationMiddleware(delay === undefined ? {} : { queryDelayMs: delay })
  const server = createServer((req, res) => middleware(req, res, () => { res.writeHead(404); res.end() }))
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${(server.address() as { port: number }).port}/api/registration`
  return { base, close: async () => { middleware.dispose(); await new Promise<void>(resolve => server.close(() => resolve())) } }
}
let host: Awaited<ReturnType<typeof start>>
beforeAll(async () => { host = await start(0) })
afterAll(async () => { await host.close() })
async function client(base = host.base) {
  const response = await fetch(base + '/session', { method: 'POST' })
  const cookie = response.headers.get('set-cookie')!.split(';')[0]!
  return (path: string, data?: unknown, actor = 'admin') => fetch(base + path, { method: data === undefined ? 'GET' : 'POST', headers: { cookie, 'X-Demo-Actor': actor, 'Content-Type': 'application/json' }, ...(data === undefined ? {} : { body: JSON.stringify(data) }) })
}
const root = '/quality/certificates', first = 'demo-person-1-certificate-1'
it('persists server records and staged attachment references across requests, isolating sessions and owners', async () => {
  const call = await client(), isolated = await client(), draftId = randomUUID(), path = `/attachment-drafts/${draftId}`, scope = { scope: 'certificate', recordId: '' }
  const uploaded = await call(path + '/upload', { ...scope, file: { id: randomUUID(), name: 'proof.txt', type: 'text/plain', size: 3, dataUrl: 'data:text/plain;base64,YWJj' } })
  expect(uploaded.status).toBe(200)
  const file = await uploaded.json(); expect(file.dataUrl).toBe('')
  const data = { personId: 'demo-person-1', category: '材料', number: 'HTTP-C', notes: '保存', files: [file], attachmentDraftId: draftId }
  expect((await call(root + '/certificates', { ...data, number: '' })).status).toBe(422)
  expect(await (await call(path + '/file', { ...scope, fileId: file.id })).text()).toBe('abc')
  const response = await call(root + '/certificates', data); expect(response.status).toBe(200)
  const saved = await response.json(), detailPath = root + '/certificates/' + saved.id
  expect(await (await call(detailPath)).json()).toMatchObject({ number: 'HTTP-C', files: [{ id: file.id, dataUrl: '' }] })
  expect(await (await call(`${detailPath}/files/${file.id}`)).text()).toBe('abc')
  expect((await isolated(detailPath)).status).toBe(404)
  expect((await call(`${root}/certificates/${first}/files/${file.id}`)).status).toBe(404)
  expect((await call(detailPath, undefined, 'analyst')).status).toBe(403)
  expect((await call(path + '/file', { ...scope, fileId: file.id })).status).toBe(422)
  // Existing references can be edited/downloaded/removed without creating a new upload draft.
  const editDraft = `/attachment-drafts/${randomUUID()}`, editScope = { scope: 'certificate', recordId: saved.id, fileId: file.id }
  expect(await (await call(editDraft + '/file', editScope)).text()).toBe('abc')
  expect((await call(editDraft + '/remove', editScope)).status).toBe(200)
  expect((await (await call(detailPath)).json()).files).toHaveLength(1)
  const edited = await call(detailPath + '/save', { ...saved, number: 'HTTP-LAST' })
  expect(edited.status).toBe(200)
  expect((await call(detailPath + '/save', { ...saved, number: 'HTTP-LAST' })).status).toBe(200)
  const query = await (await call(root + '/certificates/query', { scope: 'all', filters: { number: 'HTTP' } })).json()
  expect(query).toMatchObject({ total: 1, items: [{ number: 'HTTP-LAST' }] })
  expect(await (await call(root + '/certificates/export', { scope: 'all', filters: { number: 'HTTP' }, columns: ['name', 'number'] })).text()).toContain('HTTP-LAST')
  const latest = await (await call(detailPath)).json()
  expect((await call(root + '/projects', { certificateIds: [saved.id, first], code: 'HTTP-P', item: '接口项目' })).status).toBe(200)
  expect((await call(detailPath + '/delete', latest)).status).toBe(422)
  expect((await call(detailPath + '/delete', await (await call(detailPath)).json())).status).toBe(200)
  expect((await call(detailPath)).status).toBe(404)
  expect((await (await call(root + '/projects/query', { parentIds: [first], filters: { code: 'HTTP-P' } })).json()).total).toBe(1)
})
it('uses the existing default two-second backend delay', async () => {
  const delayed = await start()
  try {
    const call = await client(delayed.base), started = performance.now()
    const response = await call(root + '/people/query', {})
    expect(response.status).toBe(200)
    expect(performance.now() - started).toBeGreaterThanOrEqual(1900)
    expect(await response.json()).toMatchObject({ total: 12, page: 1, pageSize: 5 })
  } finally { await delayed.close() }
}, 15000)
