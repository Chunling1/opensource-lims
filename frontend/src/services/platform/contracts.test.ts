import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { platformRequest, PlatformError, setToken, hasSession } from './http'
import { mapCommission, mapSample, mapReportStage, pageRows, platformAdapter, listBindings, commissionPayload } from './adapter'
import { readFileSync } from 'node:fs'
import { backendPath } from './backendClient'
import { backendCatalog } from './backendCatalog'
import { pageAvailability, preventUnavailableNavigation } from './availability'
import { requiredPermission } from './permissions'
const response = (data: unknown, code = 0, status = 200) => new Response(JSON.stringify({ code, message: '平台返回消息', data }), { status, headers: { 'content-type': 'application/json' } })
beforeEach(() => { setToken(''); vi.stubGlobal('window', { dispatchEvent: vi.fn() }); vi.stubGlobal('fetch', vi.fn()) })
afterEach(() => vi.unstubAllGlobals())
describe('current platform workflow availability', () => {
  it('blocks both the removed report-check menu and bookmarked detail routes without borrowing interim-report permissions', () => {
    for (const path of ['/reports/check', '/reports/check/R-001']) {
      expect(pageAvailability(path).status).toBe('removed')
      expect(requiredPermission(path)).toBeUndefined()
      const event = new Event('click', {cancelable:true})
      preventUnavailableNavigation(event, path)
      expect(event.defaultPrevented).toBe(true)
    }
  })
  it('does not mislabel unfinished adapters as removed backend capabilities', () => {
    expect(pageAvailability('/reports/print')).toMatchObject({status:'pending'})
    expect(pageAvailability('/reports/checking').status).toBe('pending')
    expect(pageAvailability('/reports/review').status).toBe('available')
    expect(requiredPermission('/reports/review')).toBe('report.review.view')
    const event = new Event('click', {cancelable:true})
    preventUnavailableNavigation(event, '/reports/query')
    expect(event.defaultPrevented).toBe(false)
  })
})
describe('platform transport contract (isolated unit fixtures, not live acceptance)', () => {
  it('sends real Bearer, unwraps data, never sends demo actor', async () => {
    setToken('unit-token'); vi.mocked(fetch).mockResolvedValue(response({ rows: [] }))
    expect(await platformRequest('/api/entrust/query', { method: 'POST', body: {} })).toEqual({ rows: [] })
    const [url, init] = vi.mocked(fetch).mock.calls[0]!
    expect(url).toBe('/api/entrust/query'); expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer unit-token')
    expect(new Headers(init?.headers).has('X-Demo-Actor')).toBe(false)
  })
  it('does not transmit a stale token during login', async () => {
    setToken('old'); vi.mocked(fetch).mockResolvedValue(response({ token: 'new' }))
    await platformRequest('/api/auth/login', { method: 'POST', anonymous: true, body: {} })
    expect(new Headers(vi.mocked(fetch).mock.calls[0]![1]?.headers).has('Authorization')).toBe(false)
  })
  it.each([1,2,3,401,403,409,503])('rejects HTTP 200 business failure %s', async code => {
    vi.mocked(fetch).mockResolvedValue(response({ mustChangePassword: true }, code))
    await expect(platformRequest('/api/auth/login')).rejects.toMatchObject({ platformCode: code, data: { mustChangePassword: true } })
  })
  it('clears an expired session and notifies the login gate', async () => {
    setToken('expired'); vi.mocked(fetch).mockResolvedValue(response(null,401))
    await expect(platformRequest('/api/auth/profile')).rejects.toBeInstanceOf(PlatformError)
    expect(hasSession()).toBe(false); expect(window.dispatchEvent).toHaveBeenCalled()
  })
  it('does not turn a JSON business failure into a downloadable file', async () => {
    vi.mocked(fetch).mockResolvedValue(response(null,403))
    await expect(platformRequest('/api/reports/a/cover',{blob:true})).rejects.toMatchObject({code:'FORBIDDEN'})
  })
  it('rejects SPA fallback HTML instead of pretending it is API data', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response('<html>SPA</html>',{headers:{'content-type':'text/html'}}))
    await expect(platformRequest('/api/entrust/query')).rejects.toMatchObject({code:'UNAVAILABLE'})
  })
  it('retains abort semantics without falling back to demo data', async () => {
    const controller = new AbortController(); controller.abort(); vi.mocked(fetch).mockRejectedValue(controller.signal.reason)
    await expect(platformRequest('/api/entrust/query',{signal:controller.signal})).rejects.toBe(controller.signal.reason)
  })
})
describe('mapping and pagination', () => {
  it('maps recall visibility without overwriting the backend current status or inventing review dates', () => {
    const row=mapReportStage({reportNo:'R1',sampleNo:'S1',sampleRegState:'登记完成',status:'待批准',dataStatus:'报告批准中',rowProjection:'recall',entrustDate:'2026-10-14'},'review')
    expect(row).toMatchObject({checkStatus:'已审核',dataStatus:'报告批准中',checkDate:'',canCheck:false})
    expect(pageRows([row],{stage:'review',status:'报告审核完成',checkStatus:'已审核'}).total).toBe(1)
    expect(pageRows([row],{stage:'review',status:'报告审核中'}).total).toBe(0)
    expect(()=>mapReportStage({reportNo:'R',sampleNo:'S',sampleRegState:'登记完成'},'review')).toThrow('投影')
  })
  it('rejects old links filtering absent review/testing dates before making any request', async () => {
    await expect(platformAdapter('/samples/report-check/query','POST',{stage:'review',dateField:'testEndDate',from:'2026-01-01'})).rejects.toThrow('委托日期')
    expect(fetch).not.toHaveBeenCalled()
  })
  it('uses the backend numeric entrust id separately from the business number', () => {
    expect(mapCommission({id:7,entrustNo:'WT-123',status:'委托完成',projectName:'工程',sampleCount:2,amount:'',entrustDate:'2026-10-14'})).toMatchObject({id:'7',code:'WT-123',status:'已完成',sampleCount:2,receivableAmount:null,commissionDate:'2026-10-14'})
  })
  it('does not treat a report document version as a numeric optimistic lock', () => {
    const mapped=mapSample({reportNo:'R/中文',sampleNo:'S1',sampleRegState:'登记完成',version:'V3',entrustId:7,entrustNo:'WT-123'})
    expect(mapped).toMatchObject({id:'R/中文',code:'S1',commissionId:'7',platformDocumentVersion:'V3',version:0,canComplete:false})
  })
  it('rejects unknown sample states rather than displaying them as completed', () => {
    expect(()=>mapSample({reportNo:'R',sampleNo:'S',sampleRegState:'未知'})).toThrow()
  })
  it('filters the complete scoped dataset before calculating total and page', () => {
    const rows=Array.from({length:12},(_,i)=>({id:String(i),code:`S${i}`,customer:i%2?'甲':'乙',commissionDate:'2026-10-14'}))
    expect(pageRows(rows,{customer:'甲',page:2,pageSize:2})).toMatchObject({total:6,items:[{id:'5'},{id:'7'}]})
  })
  it('uses server page metadata instead of demanding the whole dataset', async () => {
    vi.mocked(fetch).mockResolvedValue(response({rows:[],total:2,page:2,pageSize:10}))
    await expect(platformAdapter('/commissions/query','POST',{page:2,pageSize:10})).resolves.toMatchObject({items:[],total:2,page:2})
    expect(JSON.parse(vi.mocked(fetch).mock.calls[0]![1]!.body as string)).toMatchObject({serverPage:true,page:2,pageSize:10})
  })
  it('never ignores unsupported nonempty filters', () => {
    expect(()=>pageRows([],{advanced:{code:'abc'}})).toThrow('advanced')
    expect(()=>pageRows([],{plans:{planIds:['p1']}})).toThrow('方案')
  })
  it('refuses an unmapped write before sending any request', async () => {
    await expect(platformAdapter('/samples/R/actions','POST',{actionId:'complete'})).rejects.toMatchObject({code:'UNAVAILABLE'})
    expect(fetch).not.toHaveBeenCalled()
  })
  it('preserves backend extension metadata when preparing an entrust update', () => {
    const body=commissionPayload({name:'新工程',customer:'客户',contract:'HT1',contact:'联系人',bankAccount:'123',handlingDepartmentId:'检测部'}, {projectType:'检测',info:{legacyMigration:{reviewRequired:true},unknownField:'keep',consignor:'旧'}})
    expect(body).toMatchObject({projectName:'新工程',contractNo:'HT1',department:'检测部',info:{legacyMigration:{reviewRequired:true},unknownField:'keep',consignor:'联系人',account:'123'}})
    expect(body).not.toHaveProperty('entrustNo'); expect(body).not.toHaveProperty('amount')
  })
  it('does not turn the removed report-check stage into interim-report review', async () => {
    await expect(platformAdapter('/samples/report-check/query','POST',{stage:'check'})).rejects.toMatchObject({code:'UNAVAILABLE'})
    expect(fetch).not.toHaveBeenCalled()
  })
  it('rejects edits that have no source snapshot to preserve unknown fields', async () => {
    await expect(platformAdapter('/commissions/999999','PUT',{input:{name:'x'}})).rejects.toMatchObject({code:'VERSION_CONFLICT'})
    expect(fetch).not.toHaveBeenCalled()
  })
  it('every enabled HTTP method/path is present in the backend catalog', () => {
    const keys = new Set(Object.keys(backendCatalog))
    for (const binding of Object.values(listBindings)) expect(keys.has(`POST ${binding.path}`)).toBe(true)
  })
  it('route catalog preserves API prefixes and query serialization', () => {
    expect(Object.keys(backendCatalog).length).toBeGreaterThan(200)
    expect(backendPath('GET /api/auth/security/login-records',{}, {page:2})).toBe('/api/auth/security/login-records?page=2')
  })
  it('encodes string parameters and rejects wrong numeric ids before network access', () => {
    expect(backendPath('GET /api/reports/<report_no>',{report_no:'LAB-2026-中文(E)'})).toBe('/api/reports/LAB-2026-%E4%B8%AD%E6%96%87(E)')
    expect(()=>backendPath('PUT /api/entrust/<int:eid>',{eid:'WT-001'})).toThrow('整数')
    expect(()=>backendPath('GET /api/reports/<report_no>',{})).toThrow('缺少')
  })
  it('independent base is applied exactly once to public scripts', () => {
    const html=readFileSync(new URL('../../../index.html',import.meta.url),'utf8')
    expect(html).not.toContain('%BASE_URL%'); expect(html).not.toContain('/template/'); expect(html).toContain('src="/src/main.ts"')
  })
})
