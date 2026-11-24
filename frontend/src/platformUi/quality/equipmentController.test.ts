import {readFileSync} from 'node:fs'
import ts from 'typescript'
import {parse} from '@vue/compiler-sfc'
import {expect,it,vi} from 'vitest'

const source=parse(readFileSync('src/modules/pages/EquipmentLedgerPage.vue','utf8')).descriptor.scriptSetup!.content
const ast=ts.createSourceFile('equipment.ts',source,ts.ScriptTarget.Latest,true)
function controller(name:string,context:Record<string,unknown>){
 const fn=ast.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text===name)!
 const js=ts.transpileModule(fn.getText(ast),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
 return new Function(...Object.keys(context),js+`;return ${name}`)(...Object.values(context)) as ()=>Promise<void>
}

it('sends only changed fields and current version; keeps unrelated fields out',async()=>{
 const initial={id:1,editVersion:4,archiveNo:'QA',name:'Meter',actualCalDate:'2026-01-01',lastCalDate:'2025-01-01',planCalDate:'2026-12-31',keeper:'Old',calibrationMode:'correction'}
 const updateEquipment=vi.fn(async()=>({...initial,keeper:'New',editVersion:5}))
 const ctx={form:{value:{...initial,keeper:'New'}},initialSnapshot:{value:initial},normalizeDateText:(x:string)=>x,saving:{value:false},detailOpen:{value:true},page:{value:2},updateEquipment,createEquipment:vi.fn(),reload:vi.fn(),ElMessage:{success:vi.fn(),warning:vi.fn(),error:vi.fn()}}
 await controller('save',ctx)()
 expect(updateEquipment).toHaveBeenCalledWith(1,{archiveNo:'QA',name:'Meter',editVersion:4,calibrationMode:'correction',keeper:'New'})
 expect(ctx.initialSnapshot.value.editVersion).toBe(5)
})

it('does not write when selecting a workbook, then confirms explicitly',async()=>{
 const file=new File(['synthetic'],'ledger.xlsx'),preview={createdCount:1,updatedCount:2,unchangedCount:3,changes:[]}
 const importEquipment=vi.fn(async()=>preview)
 const ctx={importEquipment,importing:{value:false},importPreview:{value:undefined},importFile:{value:undefined},importPreviewOpen:{value:false},reload:vi.fn(),ElMessage:{success:vi.fn(),error:vi.fn()}}
 const fn=controller('handleImport',ctx) as (event:unknown)=>Promise<void>
 await fn({target:{files:[file],value:'ledger.xlsx'}})
 expect(importEquipment).toHaveBeenCalledExactlyOnceWith(file,true)
 expect(ctx.importPreviewOpen.value).toBe(true)
 expect(ctx.reload).not.toHaveBeenCalled()
 await controller('confirmImport',ctx)()
 expect(importEquipment).toHaveBeenLastCalledWith(file)
 expect(ctx.importPreviewOpen.value).toBe(false)
})
