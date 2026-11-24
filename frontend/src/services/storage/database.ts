import { AppError } from '../common/errors'
import { categories, customers, projects } from '../business/dictionaries'
import { initialFields, moduleMap } from '../business/modules'
import type { BusinessRecord, Fields, LimsDatabase } from '../../types/lims'
import type { Sample } from '../../types/sample'

export const DB_NAME = 'lims.workspace.v2'
import { demoActors } from './demoActors'
export { demoActors } from './demoActors'
function seedSamples(): Sample[] {
  const names = ['地表水监测样品', '饮用水出厂样', '土壤混合样', '原料成分分析样', '食品留样', '复合材料试片']
  return Array.from({ length: 26 }, (_, i) => {
    const at = new Date(Date.now() - i * 7 * 3600000).toISOString()
    const status = i % 7 === 0 ? 'returned' : i % 3 === 0 ? 'received' : 'pending'
    const events: Sample['events'] = [{ id: `seed-${i}-created`, action: 'created', actor: '演示用户', at }]
    if (status !== 'pending') events.push({ id: `seed-${i}-status`, action: status, actor: '演示用户', at, ...(status === 'returned' ? { reason: '样品标签与送检信息不一致，请核对后重新提交。' } : {}) })
    return { id: `demo-${i + 1}`, code: `SP${at.slice(0, 10).replaceAll('-', '')}-${String(100 + i).padStart(4, '0')}`, name: `${names[i % names.length]} ${String(i + 1).padStart(2, '0')}`, category: categories[i % categories.length]!, customer: customers[i % customers.length]!, contact: ['张老师', '李工', '陈老师'][i % 3]!, phone: '13800000000', quantity: i % 4 + 1, unit: '份', projects: [projects[i % projects.length]!, projects[(i + 1) % projects.length]!], storage: i % 2 ? '常温、避光' : '2–8°C 冷藏', notes: '演示样品数据，用于验证登记与接收流程。', status, createdAt: at, updatedAt: at, events }
  })
}

export function seedDatabase(): LimsDatabase {
  const now = new Date().toISOString(), valid = `${new Date().getFullYear() + 2}-12-31`
  const records: BusinessRecord[] = []
  const add = (kind: string, id: string, name: string, data: Fields, status = '有效') => records.push({ id, kind, code: `${moduleMap[kind]!.prefix}-${String(records.length + 1).padStart(4, '0')}`, name, status, version: 1, departmentId: 'lab', ownerId: 'admin', createdAt: now, updatedAt: now, data: { ...initialFields(moduleMap[kind]!), ...data } })
  add('departments', 'lab', '中心实验室', { manager: '陈批准' }); add('departments', 'lab2', '第二实验室', { manager: '王复核' })
  add('sites', 'site', '中心检测场所', { departmentId: 'lab', address: '示范路 1 号', conditions: '恒温恒湿' })
  customers.forEach((name, i) => add('customers', `customer-${i}`, name, { contact: '张老师', phone: '13800000000', creditLimit: 100000, creditDays: 30, creditUntil: valid }))
  projects.forEach((name, i) => {
    add('projects', `project-${i}`, name, { unit: i ? 'mg/L' : 'pH', resultType: '定量', precision: 2, lower: i ? 0 : 6, upper: i ? 10 : 9, price: 100 + i * 50, laborCost: 30 })
    add('methods', `method-${i}`, `${name}通用演示方法`, { projectId: `project-${i}`, standard: `DEMO-${i + 1}`, revision: '1.0', formula: 'x', recordFields: '环境温度,前处理记录', tableColumns: '读数,说明', validUntil: valid })
  })
  add('personnel', 'person-admin', '演示用户能力授权', { actorId: 'admin', position: '管理员', projectIds: projects.map((_, i) => `project-${i}`), validUntil: valid, qualification: '演示授权' })
  add('personnel', 'person-analyst', '李检测能力授权', { actorId: 'analyst', position: '检测员', projectIds: projects.map((_, i) => `project-${i}`), validUntil: valid, qualification: '演示考核合格' })
  add('equipment', 'equipment-1', '多参数分析仪', { serial: 'DEMO-001', model: '通用型', location: '中心实验室', validUntil: valid, checkUntil: valid, condition: '正常' })
  add('locations', 'location-1', '样品冷藏柜 A', { room: '样品室', conditions: '2–8°C', capacity: 1000 })
  add('suppliers', 'supplier-1', '示范供应商', { contact: '周经理', qualification: '通用检测及物资供应', validUntil: valid, score: 90, evaluation: '演示评价合格' })
  add('inventory', 'lot-1', '检测标准溶液', { type: '标准物质', batch: 'LOT-001', quantity: 100, unit: 'mL', unitCost: 2, validUntil: valid, certificate: 'CRM-DEMO', supplierId: 'supplier-1' })
  add('reportTemplates', 'template-1', '通用检测报告', { header: '实验室信息管理系统', title: '检测报告', basicFields: ['客户', '委托编号', '样品', '方法'], resultColumns: '样品,项目,方法,结果,单位,判定', signatureLabel: '审核 / 批准', appendix: '', footer: '本报告仅对所检样品负责。' })
  demoActors.forEach(actor => add('users', actor.id, actor.name, { login: actor.id, departmentId: actor.departmentId, roles: actor.roles, scope: actor.scope }))
  add('commissions', 'demo-order-delivered', '水质送样检测委托', { customerId: 'customer-0', projectIds: ['project-0'], source: '客户送样', settlement: '预付', discount: 0, taxRate: 0, dueDate: valid, requirements: '按通用演示方法进行水质检测。' }, '草稿')
  add('commissions', 'demo-order-sampling', '现场采样检测委托', { customerId: 'customer-3', projectIds: ['project-0'], source: '现场采样', settlement: '信用', discount: 0, taxRate: 0, dueDate: valid, requirements: '安排采样后进行水质检测。' }, '草稿')
  const samples = seedSamples(), sampleMeta: LimsDatabase['sampleMeta'] = {}
  for (const sample of samples) {
    sampleMeta[sample.id] = { departmentId: 'lab', ownerId: 'admin', version: 1 }
    sample.customerId = records.find(r => r.kind === 'customers' && r.name === sample.customer)!.id
    sample.projectIds = sample.projects.map(name => records.find(r => r.kind === 'projects' && r.name === name)!.id)
  }
  return { schema: 2, revision: 0, records, samples, sampleMeta, actors: structuredClone(demoActors), audits: [], approvals: [], attachments: [] }
}
let connection: Promise<IDBDatabase> | undefined
function open() {
  if (!connection) connection = new Promise<IDBDatabase>((resolve, reject) => {
    if (typeof indexedDB === 'undefined') return reject(new AppError('STORAGE_UNAVAILABLE', '浏览器不支持 IndexedDB，数据未保存。'))
    const request = indexedDB.open(DB_NAME, 1)
    request.onupgradeneeded = () => request.result.createObjectStore('workspace')
    let abandoned = false
    request.onsuccess = () => { if (abandoned) { request.result.close(); return }; request.result.onversionchange = () => { request.result.close(); connection = undefined }; resolve(request.result) }
    request.onerror = () => { connection = undefined; reject(new AppError('STORAGE_UNAVAILABLE', '无法打开本地业务数据库，数据未保存。')) }
    request.onblocked = () => { abandoned = true; connection = undefined; reject(new AppError('STORAGE_UNAVAILABLE', '数据库升级被其他页面占用，请关闭其他页面后重试。')) }
  }).catch(cause => { connection = undefined; throw cause instanceof AppError ? cause : new AppError('STORAGE_UNAVAILABLE', '无法打开本地业务数据库，请检查浏览器设置后重试。', { cause }) })
  return connection
}
const listeners = new Set<() => void>()
let channel: BroadcastChannel | undefined
if (typeof window !== 'undefined' && typeof BroadcastChannel !== 'undefined') { channel = new BroadcastChannel(DB_NAME); channel.onmessage = () => notify(false) }
function notify(broadcast = true) { for (const fn of listeners) queueMicrotask(fn); if (broadcast) channel?.postMessage('changed') }
export function subscribeDatabase(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn) } }
let initializing: Promise<void> | undefined
async function ensure() {
  if (!initializing) initializing = (async () => {
    const db = await open()
    const existing = await new Promise<boolean>((resolve, reject) => { const t = db.transaction('workspace'); const r = t.objectStore('workspace').get('state'); r.onsuccess = () => resolve(!!r.result); r.onerror = () => reject(new AppError('STORAGE_UNAVAILABLE', '读取业务数据失败。', { cause: r.error })) })
    if (existing) return
    const initial = seedDatabase()
    await new Promise<void>((resolve, reject) => {
      const t = db.transaction('workspace', 'readwrite'), store = t.objectStore('workspace'), r = store.get('state')
      r.onsuccess = () => { try { if (!r.result) store.put(initial, 'state') } catch { t.abort() } }
      t.oncomplete = () => resolve(); t.onerror = () => reject(new AppError('STORAGE_UNAVAILABLE', '初始化数据库失败，数据未保存。')); t.onabort = t.onerror
    })
  })().catch(cause => { initializing = undefined; throw cause instanceof AppError ? cause : new AppError('STORAGE_UNAVAILABLE', '初始化本地业务数据失败，请检查浏览器设置后重试。', { cause }) })
  return initializing
}
export interface Repository { read(): Promise<LimsDatabase>; write<T>(change: (state: LimsDatabase) => T): Promise<T> }
export const repository: Repository = {
  async read(): Promise<LimsDatabase> { throw new AppError('UNAVAILABLE', '此页面的本地数据协议尚未完成平台适配，已停止读取演示数据。') },
  async write<T>(_change: (state: LimsDatabase) => T): Promise<T> { throw new AppError('UNAVAILABLE', '此操作尚未完成平台适配，未提交任何业务数据。') },
}
const disabledDemoRepository: Repository = {
  async read() {
    await ensure(); const db = await open()
    return new Promise<LimsDatabase>((resolve, reject) => { const tx = db.transaction('workspace'); const r = tx.objectStore('workspace').get('state'); r.onsuccess = () => resolve(r.result); r.onerror = () => reject(new AppError('STORAGE_UNAVAILABLE', '读取业务数据失败。')) }).catch(cause => { throw cause instanceof AppError ? cause : new AppError('STORAGE_UNAVAILABLE', '业务数据读取失败，请重试。', { cause }) })
  },
  async write<T>(change: (state: LimsDatabase) => T): Promise<T> {
    await ensure(); const db = await open()
    return new Promise<T>((resolve, reject) => {
      const storageFailure = (cause?: unknown) => new AppError('STORAGE_WRITE', '浏览器存储不可用或空间不足，数据未保存，请保留输入后重试。', { cause })
      let tx: IDBTransaction, store: IDBObjectStore, r: IDBRequest
      try { tx = db.transaction('workspace', 'readwrite'); store = tx.objectStore('workspace'); r = store.get('state') }
      catch (cause) { reject(storageFailure(cause)); return }
      let result: T, problem: unknown
      r.onsuccess = () => {
        const state = r.result as LimsDatabase
        try { result = change(state); if (result instanceof Promise) throw new AppError('INTERNAL', '事务无法完成，请稍后重试。'); state.revision++ }
        catch (e) { problem = e; tx.abort(); return }
        try { store.put(state, 'state') }
        catch (cause) { problem = storageFailure(cause); tx.abort() }
      }
      tx.oncomplete = () => { notify(); resolve(result) }
      tx.onabort = tx.onerror = () => reject(problem ?? storageFailure(tx.error))
    })
  },
}
export function memoryRepository(state = seedDatabase()): Repository {
  let current = structuredClone(state)
  return { async read() { return structuredClone(current) }, async write(change) { const next = structuredClone(current); const result = change(next); next.revision++; current = next; return structuredClone(result) } }
}
