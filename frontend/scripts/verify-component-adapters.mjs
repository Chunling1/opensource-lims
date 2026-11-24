import {readFile} from 'node:fs/promises'
import {parse} from '@vue/compiler-sfc'
import {baseParse} from '@vue/compiler-dom'
const root=new URL('../',import.meta.url)
const cases=[
 {file:'src/platformUi/reports/ReportReviewPresentation.vue',components:['SchemaForm','FormTabs','DataEntryTrialForm','BootstrapModal','PipelineWizard','EsignFlowPanel']},
 {file:'src/modules/pages/SampleRegisterPage.vue',components:['DataEntryPreview','RegistrationPresentation']},
 {file:'src/modules/pages/ContractReviewPage.vue',components:['DataEntryPreview']},
 {file:'src/modules/components/PipelineWizard.vue',components:['DataEntryPreview']},
 {file:'src/modules/components/AttachmentManagerDialog.vue',components:['DataEntryPreview']},
 {file:'src/modules/components/ReportArtifactPanel.vue',components:['DataEntryPreview']},

 {file:'src/platformUi/reports/ReportDetailPresentation.vue',components:['SchemaForm','FormTabs','BootstrapModal','DataEntryPreview','AttachmentFileList','DataTable']},
 {file:'src/modules/pages/StandardPage.vue',components:['DataEntryPreview','RegistrationPresentation']},
 {file:'src/modules/pages/PersonnelPage.vue',components:['PersonnelPresentation','BootstrapModal','SchemaForm']},
 {file:'src/modules/pages/EquipmentLedgerPage.vue',components:['EquipmentPresentation','SchemaForm']},
 {file:'src/modules/pages/StdLibraryPage.vue',components:['StandardsPresentation','SchemaForm']},
 {file:'src/modules/pages/ReportPage.vue',components:['ReportReviewPresentation','DataEntryPreview','ReportStagePresentation','ReportOutputListPresentation','ReportQueryListPresentation','ReportDetailPresentation','ReportDecisionWorkbench','BootstrapModal']},
 {file:'src/modules/pages/ReportDataEntryPage.vue',components:['EntryListPresentation','EntryRecordPresentation']},
 {file:'src/modules/components/report/ReportDecisionWorkbench.vue',components:['SchemaForm','FormTabs','DataEntryPreview','AttachmentFileList','LoadState']},
]
const failures=[],checks=[]
for(const item of cases){
 const source=await readFile(new URL(item.file,root),'utf8'),d=parse(source).descriptor,nodes=[]
 function visit(n){nodes.push(n);for(const c of n.children||[])visit(c)}visit(baseParse(d.template.content))
 const components=[]
 for(const name of item.components){
  const imported=d.scriptSetup.content.match(new RegExp(`import ${name} from ['"]([^'"]+)['"]`))?.[1],uses=nodes.filter(n=>n.tag===name)
  if(!imported||!['/components/','/platformUi/'].some(path=>imported.includes(path))||!uses.length)failures.push(`${item.file}: missing direct template component ${name}`)
  for(const node of uses)if(node.props.some(p=>p.name==='style'||p.name==='class'||p.arg?.content==='style'||p.arg?.content==='class'))failures.push(`${item.file}: visual override on ${name}`)
  components.push({name,source:imported,renderedInstances:uses.length})
 }
 checks.push({file:item.file,components})
}
for(const file of ['src/platformUi/agreementForm.ts','src/platformUi/reportEntryForm.ts','src/platformUi/quality/personnelPresentation.ts','src/platformUi/quality/equipmentPresentation.ts','src/platformUi/quality/standardsPresentation.ts','src/platformUi/commissions/registrationPresentation.ts','src/platformUi/commissions/agreementListPresentation.ts','src/platformUi/reports/reportStagePresentation.ts','src/platformUi/reports/reportOutputPresentation.ts','src/platformUi/reports/reportDetailPresentation.ts']){
 const source=await readFile(new URL(file,root),'utf8')
 if(/\b(?:class|style|fontFamily|fontSize|color|backgroundColor)\s*:/.test(source))failures.push(`${file}: visual override in field configuration`)
}
const result={scope:'Direct complete-component reuse on explicitly listed migrated surfaces only; verify:template checks their template structure separately. Does not certify unlisted surfaces or real backend writes.',checks,failures}
console.log(JSON.stringify({checks:checks.map(item=>({file:item.file,components:item.components.length})),failures}))
if(failures.length)process.exitCode=1
