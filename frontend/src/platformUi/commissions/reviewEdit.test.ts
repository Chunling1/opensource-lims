import {readFileSync} from 'node:fs'
import ts from 'typescript'
import {parse} from '@vue/compiler-sfc'
import {describe,it,expect,vi} from 'vitest'
import {reactive,ref} from 'vue'
import {useRegistrationPresentation} from './registrationPresentation'

const source=parse(readFileSync('src/modules/pages/ContractReviewPage.vue','utf8')).descriptor.scriptSetup!.content
const ast=ts.createSourceFile('review.ts',source,ts.ScriptTarget.Latest,true)
const fn=ast.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='editReviewRecord')!
const binding=ast.statements.find(n=>ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>d.name.getText(ast)==='reviewListPresentation'))!
function setup(admin=true,readOnly=false){
 const sample={reportNo:'LAB-2026H-0105'},parent={id:81,linkedSamples:[sample]}
 const ctx={reactive,ref,useRegistrationPresentation,commissionPage:{total:1},registrationSamplePage:{total:1},setRegistrationQuery:vi.fn(),exportRegistrationRows:vi.fn(),session:{canCorrectBusinessData:admin,businessReadOnly:readOnly,can:()=>true,canAction:()=>true},
  editOpen:ref(false),editMode:ref(''),editReportNo:ref(''),editParent:ref<any>(null),fetchEntrustDetail:vi.fn(async()=>({id:81,info:{projectName:'完整字段'}})),ElMessage:{error:vi.fn()},
  allRows:ref([sample]),pageName:'合同评审',route:{},reviewLinkedParents:[parent],reviewListBusy:false,reviewListError:'',reviewListSelected:ref(),selectReviewRow:vi.fn(),loadReviewLists:vi.fn()}
 const js=ts.transpileModule(fn.getText(ast)+'\n'+binding.getText(ast),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
 const model=new Function(...Object.keys(ctx),js+'; return reviewListPresentation')(...Object.values(ctx))
 return {ctx,model,sample,parent}
}
describe('contract review editing uses the registered page callbacks',()=>{
 it('opens the sample edit wizard with its exact report identity',()=>{const {ctx,model}=setup();model.navigate(model.link('samples','LAB-2026H-0105',true));expect(ctx.editOpen.value).toBe(true);expect(ctx.editReportNo.value).toBe('LAB-2026H-0105');expect(ctx.editMode.value).toBe('samples');expect(ctx.fetchEntrustDetail).not.toHaveBeenCalled()})
 it('loads full entrust data before opening editing',async()=>{const {ctx,model}=setup();model.navigate(model.link('commissions','81',true));await vi.waitFor(()=>expect(ctx.editOpen.value).toBe(true));expect(ctx.editParent.value.info.projectName).toBe('完整字段');expect(ctx.editMode.value).toBe('entrust');expect(ctx.editReportNo.value).toBe('')})
 it.each([[false,false],[true,true]])('does not open editing without correction access (%s,%s)',(admin,readOnly)=>{const {ctx,model}=setup(admin,readOnly);model.navigate(model.link('samples','LAB-2026H-0105',true));expect(ctx.editOpen.value).toBe(false);expect(model.workspaceCanEdit(null,'samples',{})).toBe(false)})
 it('keeps the form closed when details fail',async()=>{const {ctx,model}=setup();ctx.fetchEntrustDetail.mockRejectedValueOnce(new Error('无法加载'));model.navigate(model.link('commissions','81',true));await vi.waitFor(()=>expect(ctx.ElMessage.error).toHaveBeenCalledWith('无法加载'));expect(ctx.editOpen.value).toBe(false)})
})
