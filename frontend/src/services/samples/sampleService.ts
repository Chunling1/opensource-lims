import { AppError, problem } from '../common/errors'
import { categories, units } from '../business/dictionaries'
import type { Sample, SampleInput, SampleQuery, SampleAction } from '../../types/sample'
import { repository, subscribeDatabase } from '../storage/database'
import { currentActor, resolveActor, assertRole, inScope, assertScope, sessionLocked } from '../../stores/session'
import type { LimsDatabase } from '../../types/lims'
export const subscribeSampleChanges = subscribeDatabase
function actor(state: LimsDatabase) { if (sessionLocked.value) throw new AppError('LOCKED', '工作空间已锁定。'); const a = resolveActor(state, currentActor.value.id); assertRole(a, ['samples', 'commissions', 'testing', 'reviewer', 'approver']); return a }
function validate(state: LimsDatabase, input: SampleInput) {
  const data = JSON.parse(JSON.stringify(input)) as SampleInput
  data.name = data.name.trim(); data.projects = [...new Set(data.projects)]
  if (!data.name || data.name.length > 120) throw problem('VALIDATION', '请输入样品名称（不超过 120 字）。', 'name')
  const dict = (category: string) => state.records.filter(r => r.kind === 'dictionaries' && r.status === '有效' && r.data.category === category).map(r => String(r.data.value))
  if (![...categories, ...dict('样品类别')].includes(data.category)) throw problem('VALIDATION', '请选择样品类别。', 'category')
  if (!state.records.some(r => r.kind === 'customers' && r.status === '有效' && r.name === data.customer)) throw problem('VALIDATION', '请选择有效委托单位。', 'customer')
  if (!Number.isFinite(data.quantity) || data.quantity <= 0) throw problem('VALIDATION', '样品数量必须为正数。', 'quantity')
  if (![...units, ...dict('单位')].includes(data.unit)) throw problem('VALIDATION', '请选择数量单位。', 'unit')
  if (!data.projects.length || data.projects.some(p => !state.records.some(r => r.kind === 'projects' && r.status === '有效' && r.name === p))) throw problem('VALIDATION', '请至少选择一个有效检测项目。', 'projects')
  return data
}
export const sampleService = {
  async list(query: SampleQuery = {}) {
    const state = await repository.read(), a = actor(state)
    let items = state.samples.filter(s => inScope(a, state.sampleMeta[s.id] ?? { departmentId: 'lab' }))
    if (query.keyword?.trim()) items = items.filter(s => `${s.code} ${s.name}`.toLowerCase().includes(query.keyword!.trim().toLowerCase()))
    if (query.customer) items = items.filter(s => s.customer === query.customer)
    if (query.status) items = items.filter(s => s.status === query.status)
    if (query.from) items = items.filter(s => s.createdAt.slice(0,10) >= query.from!)
    if (query.to) items = items.filter(s => s.createdAt.slice(0,10) <= query.to!)
    items.sort((a,b) => b.createdAt.localeCompare(a.createdAt) || b.code.localeCompare(a.code))
    const pageSize = [10,20,50].includes(query.pageSize || 10) ? query.pageSize || 10 : 10, page = Math.min(Math.max(1, query.page || 1), Math.max(1, Math.ceil(items.length/pageSize)))
    return {items: items.slice((page-1)*pageSize,page*pageSize), total: items.length, page, pageSize}
  },
  async detail(id: string) { const state = await repository.read(), a = actor(state), s = state.samples.find(s => s.id === id); if (!s) throw new AppError('NOT_FOUND', '样品不存在或已不可访问。'); assertScope(a, state.sampleMeta[id] ?? {departmentId:'lab'}); return { ...s, version: state.sampleMeta[id]?.version ?? 1 } },
  async context(id: string) { const state = await repository.read(), a = actor(state); assertScope(a, state.sampleMeta[id] ?? { departmentId: 'lab' }); const links = state.records.filter(r => r.kind === 'sampleLinks' && r.status === '已关联' && r.data.sampleId === id); return { commissions: state.records.filter(r => links.some(l => l.data.commissionId === r.id)), movements: state.records.filter(r => r.kind === 'movements' && r.data.sampleId === id && r.status === '已完成'), tasks: state.records.filter(r => ['tasks', 'outsourcing'].includes(r.kind) && r.data.sampleId === id) } },
  async create(input: SampleInput) {
    return repository.write(state => {
      const a = actor(state); assertRole(a, ['samples','commissions']); const data = validate(state,input), at = new Date().toISOString(), stamp = at.slice(0,10).replaceAll('-','')
      let sequence = state.samples.length+1; while(state.samples.some(s => s.code === `SP${stamp}-${String(sequence).padStart(4,'0')}`)) sequence++
      const sample: Sample = {...data,id:crypto.randomUUID(),code:`SP${stamp}-${String(sequence).padStart(4,'0')}`,status:'pending',createdAt:at,updatedAt:at,events:[{id:crypto.randomUUID(),action:'created',actor:a.name,at}]}
      sample.customerId = state.records.find(r => r.kind === 'customers' && r.name === data.customer)?.id; sample.projectIds = data.projects.map(p => state.records.find(r => r.kind === 'projects' && r.name === p)!.id)
      state.samples.push(sample); state.sampleMeta[sample.id] = {departmentId:a.departmentId,ownerId:a.id,version:1}; state.audits.push({id:crypto.randomUUID(),entityId:sample.id,kind:'samples',action:'登记样品',actorId:a.id,actor:a.name,at,reason:sample.code}); return sample
    })
  },
  update: (id: string,input: SampleInput,version?: number) => mutate(id,'edited',input,undefined,version),
  receive: (id: string, version?: number) => mutate(id,'received',undefined,undefined,version),
  returnSample: (id: string,reason: string, version?: number) => mutate(id,'returned',undefined,reason,version),
  resubmit: (id: string, version?: number) => mutate(id,'resubmitted',undefined,undefined,version),
  async statistics() { const state = await repository.read(), a = actor(state); return state.samples.filter(s => inScope(a,state.sampleMeta[s.id] ?? {departmentId:'lab'})).reduce((n,s) => {n.total++;n[s.status]++;return n}, {total:0,pending:0,received:0,returned:0}) },
  async dictionaries() { const state = await repository.read(); actor(state); return { customers: state.records.filter(r => r.kind === 'customers' && r.status === '有效').map(r => r.name), projects: state.records.filter(r => r.kind === 'projects' && r.status === '有效').map(r => r.name), categories: [...categories,...state.records.filter(r => r.kind === 'dictionaries' && r.status === '有效' && r.data.category === '样品类别').map(r => String(r.data.value))], units: [...units,...state.records.filter(r => r.kind === 'dictionaries' && r.status === '有效' && r.data.category === '单位').map(r => String(r.data.value))] } },
}
function mutate(id: string,action: Exclude<SampleAction,'created'>,input?: SampleInput,reason?: string,version?: number) {
  return repository.write(state => {
    const a = actor(state); assertRole(a,['samples','commissions']); const s = state.samples.find(s => s.id === id)
    if (!s) throw new AppError('NOT_FOUND', '样品不存在或已不可访问。'); assertScope(a,state.sampleMeta[id] ?? {departmentId:'lab'})
    
    if (action === 'edited' && s.status === 'received') throw new AppError('BUSINESS_RULE', '已接收样品为只读，不能修改。')
    if (['received','returned'].includes(action) && s.status !== 'pending') throw new AppError('BUSINESS_RULE', '仅待接收样品允许执行此操作，请刷新后重试。')
    if (action === 'resubmitted' && s.status !== 'returned') throw new AppError('BUSINESS_RULE', '仅已退回样品可以重新提交。')
    if (action === 'returned' && (!reason?.trim() || reason.length > 500)) throw problem('VALIDATION', '请输入退回原因（1–500 字）。', 'reason')
    if (action === 'edited' && input) { Object.assign(s,validate(state,input)); s.customerId = state.records.find(r => r.kind === 'customers' && r.name === s.customer)?.id; s.projectIds = s.projects.map(p => state.records.find(r => r.kind === 'projects' && r.name === p)!.id) }
    if (action === 'received') s.status = 'received'
    if (action === 'returned') s.status = 'returned'
    if (action === 'resubmitted') s.status = 'pending'
    s.updatedAt = new Date().toISOString(); s.events.push({id:crypto.randomUUID(),action,actor:a.name,at:s.updatedAt,...(reason ? {reason:reason.trim()}: {})})
    const meta = state.sampleMeta[id]; if (meta) meta.version++
    state.audits.push({id:crypto.randomUUID(),entityId:id,kind:'samples',action:{edited:'编辑样品',received:'接收样品',returned:'退回样品',resubmitted:'重新提交'}[action],actorId:a.id,actor:a.name,at:s.updatedAt,reason:reason || s.code})
    return s
  })
}
