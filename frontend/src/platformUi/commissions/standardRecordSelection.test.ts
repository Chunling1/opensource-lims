import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia } from 'pinia'
vi.mock('@/services/pipeline', async original => ({ ...await original<any>(), fetchCapabilityItems: vi.fn(async () => []), fetchCapabilityPage: vi.fn(async () => ({rows:[],total:0})) }))
vi.mock('@/services/quality', async original => ({ ...await original<any>(), searchStdLib: vi.fn(), searchStdLibPage: vi.fn() }))
import { searchStdLib, searchStdLibPage } from '@/services/quality'
import Form from '@/components/PipelineWizard.vue'
import { ElMessageBox } from 'element-plus'
const code = 'EN 442-1:2014'
const cn = {id:101, code, name:'散热器和对流器', singleList:true, sites:['A']}
const en = {id:102, code, name:'Specification for radiators', singleList:false, sites:[]}
const wrappers: ReturnType<typeof shallowMount>[] = []
function setup() {
 const w=shallowMount(Form,{props:{modelValue:false,mode:'samples'},global:{plugins:[createPinia()],config:{warnHandler:()=>undefined}}})
 wrappers.push(w)
 const c=(w.vm as any).$.setupState
 Object.assign(c.s,{testDept:'虚拟部门',reportType:'产品报告',sendDate:'2026-10-29'})
 return c
}
beforeEach(()=>{
 vi.clearAllMocks()
 vi.spyOn(ElMessageBox,'confirm').mockResolvedValue('confirm')
 vi.mocked(searchStdLib).mockImplementation(async (_kw,_dept,options)=>[cn,en].filter(r=>!options?.ids||options.ids.includes(r.id)) as any)
 vi.mocked(searchStdLibPage).mockResolvedValue({rows:[cn,en],total:2,page:1,size:50} as any)
})
afterEach(()=>wrappers.splice(0).forEach(w=>w.unmount()))
it.each([cn,en])('selects and saves only record $id with its own name',async row=>{
 const c=setup();await c.openBasisDialog()
 expect(c.stdOptions).toHaveLength(2)
 c.toggleBasisDraft(row,true)
 expect(c.basisDraftItemIds).toEqual([row.id])
 expect(c.selectedBasisRow(code,c.basisDraftItemIds).id).toBe(row.id)
 await c.confirmBasisSelection()
 const saved=JSON.parse(JSON.stringify(c.currentSampleItem()))
 expect(saved.standardItemIds).toEqual([row.id])
 expect(saved.standardNames[code]).toBe(row.name)
 expect(saved.commissionText.basis).toContain(row.name)
 const reopened=setup();Object.assign(reopened.s,saved);reopened.normalizeSampleBasisState()
 expect(reopened.s.standardItemIds).toEqual([row.id])
 await reopened.hydrateStandardOptions([code]);await reopened.openBasisDialog()
 expect(reopened.basisDraftItemIds).toEqual([row.id])
 expect(reopened.selectedBasisRow(code).id).toBe(row.id)
 expect(reopened.commissionBasisText).toContain(row.name)
})
it('switches a variant only after confirming removal of its old parameters',async()=>{
 const c=setup();c.mergeStandardOptions([cn,en]);c.toggleBasisDraft(cn,true);c.toggleBasisDraft(cn,false);c.toggleBasisDraft(en,true)
 expect(c.basisDraftCodes).toEqual([code]);expect(c.basisDraftItemIds).toEqual([en.id])
 Object.assign(c.s,{testBases:[code],standardItemIds:[cn.id],capabilityEntryIds:[9],capabilitySnapshots:[{id:9,standardCode:code,itemName:'中文参数'}]})
 const {fetchCapabilityItems}=await import('@/services/pipeline')
 vi.mocked(fetchCapabilityItems).mockResolvedValue([])
 await c.confirmBasisSelection()
 expect(c.s.standardItemIds).toEqual([en.id]);expect(c.s.capabilityEntryIds).toEqual([])
 expect(ElMessageBox.confirm).toHaveBeenCalled()
 expect(c.s.testBasisSingle).toBe(false)
 c.toggleBasisDraftByCode(code,false);expect(c.basisDraftItemIds).toEqual([])
 await c.confirmBasisSelection();expect(c.s.standardItemIds).toEqual([])
})
it('does not replace an unresolved saved English ID with the Chinese search result',async()=>{
 const c=setup();Object.assign(c.s,{testBases:[code],standardItemIds:[en.id],standardNames:{[code]:en.name}})
 c.mergeStandardOptions([cn]);c.normalizeSampleBasisState()
 expect(c.s.standardItemIds).toEqual([en.id]);expect(c.commissionBasisText).toContain(en.name)
 await c.hydrateStandardOptions([code])
 expect(searchStdLib).toHaveBeenCalledWith('', '虚拟部门',expect.objectContaining({ids:[en.id]}))
 expect(c.selectedBasisRow(code).id).toBe(en.id)
 c.mergeStandardOptions([cn]);expect(c.commissionBasisText).toContain(en.name)
})
it('keeps draft cancellation isolated and legacy ambiguous codes unselected',async()=>{
 const c=setup();Object.assign(c.s,{testBases:[code],standardItemIds:[cn.id]});c.mergeStandardOptions([cn,en])
 await c.openBasisDialog();c.toggleBasisDraft(en,true);c.basisDialogOpen=false
 expect(c.s.standardItemIds).toEqual([cn.id]);await c.openBasisDialog();expect(c.basisDraftItemIds).toEqual([cn.id])
 c.s.standardItemIds=[];c.s.standardNames={};c.syncBasisFields()
 expect(c.s.standardItemIds).toEqual([]);expect(c.selectedBasisRow(code)).toBeUndefined()
})

it('retains IDs and names when removing a standard is cancelled',async()=>{
 const c=setup();c.mergeStandardOptions([cn,en]);Object.assign(c.s,{testBases:[code],standardItemIds:[en.id],standardNames:{[code]:en.name},capabilityEntryIds:[9]})
 c.capabilityOptions=[{id:9,standardCode:code,itemName:'热输出'}]
 await c.openBasisDialog();c.toggleBasisDraftByCode(code,false)
 vi.mocked(ElMessageBox.confirm).mockRejectedValueOnce('cancel')
 await c.confirmBasisSelection()
 expect(c.s.testBases).toEqual([code]);expect(c.s.standardItemIds).toEqual([en.id]);expect(c.commissionBasisText).toContain(en.name)
 expect(c.basisDialogOpen).toBe(true)
})


it('passes the selected record identity when querying parameters', async()=>{
 const c=setup();Object.assign(c.s,{testBases:[code],standardItemIds:[en.id]});c.mergeStandardOptions([cn,en])
 c.capabilityDialogOpen=true;await c.loadCapabilityCatalog({keyword:'',page:1,size:20})
 const {fetchCapabilityPage}=await import('@/services/pipeline')
 expect(fetchCapabilityPage).toHaveBeenCalledWith(expect.objectContaining({standardItemIds:[en.id],standardCodes:[code]}),expect.any(AbortSignal))
})

it('confirming a parameter never adds its historical source code as a standard', async () => {
 const c=setup(); c.mergeStandardOptions([cn,en])
 Object.assign(c.s,{testBases:[code],standardItemIds:[en.id],standardNames:{[code]:en.name},locationWorkflowVersion:1,isOnsiteTesting:false})
 c.capabilityOptions=[{id:9,standardCode:'EN 442-1',itemName:'Thermal output',address:'虚拟实验室'}]
 await c.confirmCapabilitySelection([9],[],[{kind:'library',id:9}],{})
 expect(c.s.testBases).toEqual([code]);expect(c.s.standardItemIds).toEqual([en.id])
 expect(c.s.capabilityEntryIds).toEqual([9]);expect(c.s.testLocation).toBe('虚拟实验室')
})

it('keeps both same-code IDs, names, styles, ordering and parameters through save/reopen', async()=>{
 const c=setup();await c.openBasisDialog();c.toggleBasisDraft(cn,true);c.toggleBasisDraft(en,true);c.toggleBasisDraft(cn,true)
 expect(c.basisDraftItemIds).toEqual([cn.id,en.id]);expect(c.basisDraftRecords).toHaveLength(2)
 c.reorderBasisDraft([`id:${en.id}`,`id:${cn.id}`]);await c.confirmBasisSelection()
 expect(c.s.standardItemIds).toEqual([en.id,cn.id])
 c.s.basisTitleStyles={[`id:${en.id}`]:'EN',[`id:${cn.id}`]:'CN'}
 c.s.capabilityEntryIds=[9,10];c.capabilityOptions=[{id:9,standardItemId:cn.id,standardCode:code,itemName:'中文参数'},{id:10,standardItemId:en.id,standardCode:code,itemName:'English parameter'}]
 const saved=JSON.parse(JSON.stringify(c.currentSampleItem()))
 expect(saved.commissionText.basis).toBe(`${code} <${en.name}>；${code} 《${cn.name}》`)
 const reopened=setup();Object.assign(reopened.s,saved);reopened.normalizeSampleBasisState()
 expect(reopened.s.standardItemIds).toEqual([en.id,cn.id]);expect(reopened.commissionBasisText).toBe(saved.commissionText.basis)
 await reopened.openBasisDialog();expect(reopened.basisDraftRecords.map((r:any)=>r.id)).toEqual([en.id,cn.id])
 expect(reopened.s.capabilityEntryIds).toEqual([9,10]);expect(ElMessageBox.confirm).not.toHaveBeenCalled()
})
it('adding a same-code record does not clear the first record parameters', async()=>{
 const c=setup();c.mergeStandardOptions([cn,en]);Object.assign(c.s,{testBases:[code],standardItemIds:[cn.id],capabilityEntryIds:[9]})
 await c.openBasisDialog();c.toggleBasisDraft(en,true);await c.confirmBasisSelection()
 expect(c.s.standardItemIds).toEqual([cn.id,en.id]);expect(c.s.capabilityEntryIds).toEqual([9]);expect(ElMessageBox.confirm).not.toHaveBeenCalled()
})
it('removing one language keeps the other record and its parameters, with cancel protection', async()=>{
 const {fetchCapabilityItems}=await import('@/services/pipeline')
 vi.mocked(fetchCapabilityItems).mockResolvedValue([{id:10,standardItemId:en.id,standardCode:code,itemName:'English parameter'}] as any)
 const c=setup();c.mergeStandardOptions([cn,en]);Object.assign(c.s,{testBases:[code],standardItemIds:[cn.id,en.id],capabilityEntryIds:[9,10]})
 await c.openBasisDialog();c.removeBasisDraft(`id:${cn.id}`);expect(c.basisDraftItemIds).toEqual([en.id]);expect(c.basisDraftCodes).toEqual([code])
 vi.mocked(ElMessageBox.confirm).mockRejectedValueOnce('cancel');await c.confirmBasisSelection()
 expect(c.s.standardItemIds).toEqual([cn.id,en.id]);expect(c.s.capabilityEntryIds).toEqual([9,10]);expect(c.basisDialogOpen).toBe(true)
 c.removeBasisDraft(`id:${cn.id}`);await c.confirmBasisSelection()
 expect(c.s.standardItemIds).toEqual([en.id]);expect(c.s.capabilityEntryIds).toEqual([10])
 expect(fetchCapabilityItems).toHaveBeenCalledWith(expect.objectContaining({standardItemIds:[en.id],ids:[9,10]}))
})

it('retains unresolved IDs across repeated normalization of multiple codes',async()=>{
 const c=setup();Object.assign(c.s,{testBases:[code,'JJG 229-2010'],standardItemIds:[101,102,103]})
 c.normalizeSampleBasisState();c.normalizeSampleBasisState()
 expect(c.s.standardItemIds).toEqual([101,102,103])
 c.mergeStandardOptions([cn,en,{...cn,id:103,code:'JJG 229-2010',name:'温度标准'}]);c.syncBasisFields()
 expect(c.s.standardItemIds).toEqual([101,102,103]);expect(c.s.standardRecords.map((r:any)=>r.code)).toEqual([code,code,'JJG 229-2010'])
})
