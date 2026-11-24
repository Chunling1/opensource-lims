import {describe,it,expect} from 'vitest'
import {mount} from '@vue/test-utils'
import {reactive,h} from 'vue'
import SchemaForm from '../components/forms/SchemaForm.vue'
import {createReportEntrySchema,type ReportEntryForm} from './reportEntryForm'
import {runReportUpload,templateAttachments} from './reportAttachments'

const model=()=>reactive<ReportEntryForm>({temperature:'',pressure:'',humidity:'',calibrationPlace:'',resultStatus:'',unqualifiedParams:'',recordNo:'',result:'',conclusion:'',remark:''})
function render(data:ReportEntryForm,calibration=false,readonly=false){
 const schema=createReportEntrySchema({isCalibrationReport:calibration,entryStaffDisplay:'主检 A'})
 const slots=Object.fromEntries(schema.sections.flatMap(s=>s.fields.flatMap(f=>f.control==='custom'?[[f.slot,()=>h('span','业务控件')]]:[])))
 return mount(SchemaForm as any,{props:{schema,model:data,readonly},slots})
}
describe('Report entry data adapter',()=>{
 it('retains 22 field groups and uses template sections with no font/color/style configuration',()=>{
  const schema=createReportEntrySchema({isCalibrationReport:false,entryStaffDisplay:'A'})
  expect(schema.sections.flatMap(s=>s.fields)).toHaveLength(22)
  for(const field of schema.sections.flatMap(s=>s.fields))expect(Object.keys(field).filter(k=>/class|style|font|color/i.test(k))).toEqual([])
  const wrapper=render(model());expect(wrapper.findAll('section.card > .card-body > .row.g-3')).toHaveLength(3)
 })
 it('preserves range/string values and conditional calibration fields',async()=>{
  expect(render(model()).find('#report-entry-field-6').exists()).toBe(false)
  const data=model(),wrapper=render(data,true)
  await wrapper.get('#report-entry-field-6').setValue('26.6～27.4');expect(data.temperature).toBe('26.6～27.4')
  await wrapper.get('#report-entry-field-19').setValue('0.0328 W/(m·K)');expect(data.result).toBe('0.0328 W/(m·K)')
 })
 it('shows unqualified parameters only for the existing failing business status without erasing hidden data',async()=>{
  const data=model();data.unqualifiedParams='参数 A';const wrapper=render(data)
  expect(wrapper.find('#report-entry-field-17').exists()).toBe(false)
  data.resultStatus='判定不合格';await wrapper.vm.$nextTick()
  expect((wrapper.get('#report-entry-field-17').element as HTMLInputElement).value).toBe('参数 A')
 })
 it('blocks readonly model changes and editing the inherited entry person',async()=>{
  const data=model(),wrapper=render(data,false,true)
  await wrapper.get('#report-entry-field-21').setValue('不应保存');expect(data.remark).toBe('')
  expect((wrapper.get('#report-entry-field-11').element as HTMLInputElement).disabled).toBe(true)
 })
})
describe('Template upload and attachment adaptation',()=>{
 it('resolves only when the existing controller confirms upload success',async()=>{
  const file=new File(['report'],'report.pdf')
  await expect(runReportUpload(file,async request=>{expect(request.file).toBe(file);request.onSuccess?.()})).resolves.toBeUndefined()
 })
 it('does not convert caught backend errors or cancelled replacement into success',async()=>{
  const file=new File(['report'],'report.pdf'),error=new Error('后端拒绝：权限不足')
  await expect(runReportUpload(file,async request=>{request.onError?.(error)})).rejects.toBe(error)
  await expect(runReportUpload(file,async()=>{})).rejects.toThrow('操作已取消或报告已切换')
 })
 it('preserves numeric backend IDs, eligibility and source object for list actions',()=>{
  const source={id:81,name:'附件.pdf',type:'PDF',source:'其他附件',status:'有效',mergeEligible:false,selectedForOfficial:false,sizeBytes:123}
  const [file]=templateAttachments([source]);expect(file.id).toBe('81');expect(file.source).toBe(source);expect(file.source.mergeEligible).toBe(false);expect(file.size).toBe(123)
 })
})
