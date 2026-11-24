import {describe,it,expect} from 'vitest'
import {reactive,ref} from 'vue'
import {reportOpinionSchema,reportDocumentSchema,reportTestSchema,reportVersionRows,reportFiles} from './reportDetailPresentation'
const field=(schema:any,id:string)=>schema.sections.flatMap((s:any)=>s.fields).find((f:any)=>f.id===id)
describe('Report detail uses original business models',()=>{
 it('opinion writes through the controller ref and retains read-only/node constraints',()=>{
  const opinion=ref('原意见'),c=reactive({opinion,pageName:'报告归档',formReadOnly:false,canActOnSelected:true,session:{userName:'审核员',roleName:'报告'},nodeActions:{editableScope:'意见',returnTargets:['检测数据更改']}})
  field(reportOpinionSchema(c),'report-opinion').binding.set(c,'新的归档意见');expect(opinion.value).toBe('新的归档意见')
  c.formReadOnly=true;expect(field(reportOpinionSchema(c),'report-opinion').disabled).toBe(true)
  c.formReadOnly=false;c.canActOnSelected=false;expect(field(reportOpinionSchema(c),'report-opinion').disabled).toBe(true)
 })
 it('document fields edit the original group, result, photo ID and remarks without submitting',()=>{
  const c={editDocument:{resultGroups:[{name:'热工',items:[{name:'导热系数',condition:'20℃',unit:'W',value:'1'}]}],photos:[{attachmentId:15,caption:'铭牌'}],remarks:'原备注'},imageAttachments:[{id:15,name:'铭牌.png'},{id:27,name:'设备.png'}]}
  const schema=reportDocumentSchema(c)
  field(schema,'report-edit-0-0-value').binding.set(c.editDocument,'2.50');field(schema,'report-edit-photo-file-0').binding.set(c.editDocument,'27');field(schema,'report-remarks').binding.set(c.editDocument,'复核')
  expect(c.editDocument.resultGroups[0].items[0]).toEqual({name:'导热系数',condition:'20℃',unit:'W',value:'2.50'});expect(c.editDocument.photos[0].attachmentId).toBe(27);expect(c.editDocument.remarks).toBe('复核')
 })
 it('preserves test field values, conditional failure parameters and source objects for downloads',()=>{
  const testInfo={resultStatus:'不合格',unqualifiedParams:'温度'},s=reportTestSchema({testInfo});expect(field(s,'report-unqualifiedParams').visible).toBe(true)
  field(s,'report-unqualifiedParams').binding.set(testInfo,'温度、压力');expect(testInfo.unqualifiedParams).toBe('温度、压力')
  const version={id:5,outputKind:'official',sourceVerification:'unavailable',stale:false},attachment={id:7,name:'记录.pdf',type:'原始记录',size:123};
  const c={documentVersions:[version],currentAttachments:[attachment]};expect(reportVersionRows(c)[0].source).toBe(version);expect(reportVersionRows(c)[0].state).toBe('源数据待核实');expect(reportFiles(c)[0].source).toBe(attachment)
 })
})
