import {describe,it,expect,vi} from 'vitest'
import {reactive,nextTick} from 'vue'
import {mount} from '@vue/test-utils'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import {equipmentSchema,equipmentBatchForm,createEquipmentPresentation} from './equipmentPresentation'
import {standardSchema,masterStandardSchema,createStandardsPresentation} from './standardsPresentation'
import {esignSchema} from './personnelPresentation'
describe('Quality full-template business bindings',()=>{
 it('same-number equipment selection, edit and export retain distinct IDs',async()=>{
  const c=reactive<any>({rows:[{id:12,archiveNo:'GN26',name:'电子天平'},{id:13,archiveNo:'GN26',name:'Electronic balance'}],depts:[],selected:[],canEquipmentExport:true,exportRows:vi.fn(),openDetail:vi.fn(),openCreate:vi.fn(),session:{}})
  const m=createEquipmentPresentation(c)
  m.selected=['13'];await nextTick()
  expect(c.selected.map((r:any)=>r.id)).toEqual([13])
  m.modal={mode:'edit',recordId:'13'}
  expect(c.openDetail).toHaveBeenCalledWith(c.rows[1],false)
  expect(c.openCreate).not.toHaveBeenCalled()
  m.exportRows(true)
  expect(c.exportRows).toHaveBeenLastCalledWith([13])
  m.selected=['12','13'];await nextTick();m.exportRows(true)
  expect(c.exportRows).toHaveBeenLastCalledWith([12,13])
  m.exportRows(false)
  expect(c.exportRows).toHaveBeenLastCalledWith()
 })
 it('empty selected export cannot fall back to exporting all instruments',()=>{
  const c=reactive<any>({rows:[],depts:[],selected:[],canEquipmentExport:true,exportRows:vi.fn(),session:{}})
  createEquipmentPresentation(c).exportRows(true)
  expect(c.exportRows).not.toHaveBeenCalled()
 })
 it('covers every original equipment field and invokes calibration hooks',async()=>{const model=reactive<any>({period:'1年',planCalDate:'2026-10-15'}),fn=vi.fn(),schema=equipmentSchema({depts:['科室'],recalculateNextDate:fn});const w=mount(SchemaForm as any,{props:{model,schema}});expect(schema.sections[0]!.fields).toHaveLength(25);await w.get('#equipment-actualCalDate').setValue('2026-11-12');expect(model.actualCalDate).toBe('2026-11-12');await w.get('#equipment-period').setValue('2年');expect(model.period).toBe('2年');expect(fn).toHaveBeenCalledTimes(2);expect(model.planCalDate).toBe('2026-10-15')});
 it('batch controls do not implicitly enable edits or erase unchecked values',async()=>{const enabled=reactive({dept:false,period:false}),model=reactive({dept:'保留部门',period:'1年'}),w=mount(SchemaForm as any,{props:{model,schema:equipmentBatchForm({depts:['保留部门'],batchEnabled:enabled})}});expect(w.get('#equipment-dept').attributes('disabled')).toBeDefined();await w.get('#enable-dept').setValue(true);expect(enabled.dept).toBe(true);expect(model.dept).toBe('保留部门');expect(enabled.period).toBe(false)});
 it('keeps authorization department arrays and boolean standard values, readonly blocks edits',async()=>{const model=reactive<any>({code:'X',name:'标准',useDepts:['甲'],isEnglish:false}),schema=standardSchema({depts:['甲','乙'],canAuthorize:true}),w=mount(SchemaForm as any,{props:{model,schema}});await w.get('#std-dept-1').setValue(true);await w.get('#std-isEnglish').setValue(true);expect(model.useDepts).toEqual(['甲','乙']);expect(model.isEnglish).toBe(true);await w.setProps({readonly:true});expect(w.get('#std-dept-0').attributes('disabled')).toBeDefined();expect(masterStandardSchema().sections[0]!.fields.map(x=>x.id)).toContain('std-expired')});
 it('readonly identity binding leaves the underlying signature account unchanged',()=>{const model={esignLegalName:'甲',esignAccountInput:'',esignBindingStatus:'未绑定'},w=mount(SchemaForm as any,{props:{model,schema:esignSchema({}),readonly:true},slots:{binding:'<button disabled>绑定</button>'}});expect(w.get('#esign-phone').attributes('readonly')).toBeDefined();expect(model.esignAccountInput).toBe('')});
 it('equipment row selection reaches original bulk controller with numeric IDs',async()=>{const c=reactive<any>({rows:[{id:12,archiveNo:'E12'}],depts:[],selected:[],canEquipmentBatchUpdate:true,openBatch:vi.fn(),session:{}}),m=createEquipmentPresentation(c);m.selected=['12'];await nextTick();m.openBatch(0);expect(c.selected[0].id).toBe(12);expect(c.openBatch).toHaveBeenCalledOnce()});
 it('standard dataset switch and readonly action use separate backend controllers',()=>{const c=reactive<any>({rows:[],masterRows:[{id:3,code:'M3'}],depts:[],datasetMode:'controlled',session:{can:()=>true,canAction:()=>true},onDatasetChange:vi.fn(),openMasterEdit:vi.fn()}),m=createStandardsPresentation(c);m.action(0);expect(c.datasetMode).toBe('master');expect(c.onDatasetChange).toHaveBeenCalledOnce();m.modal={mode:'view',row:{source:c.masterRows[0]}};expect(c.masterViewOnly).toBe(true);expect(c.openMasterEdit).toHaveBeenCalledWith(c.masterRows[0]);expect(m.modal).toBeUndefined()});
})
