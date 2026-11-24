import {describe,it,expect} from 'vitest'
import {readFileSync} from 'node:fs'
import {parse} from '@vue/compiler-sfc'
import ts from 'typescript'

const script=parse(readFileSync('src/modules/pages/ReportDataEntryPage.vue','utf8')).descriptor.scriptSetup!.content
function request(corrector:boolean,change:boolean,query:Record<string,any>){
 const ast=ts.createSourceFile('page.ts',script,ts.ScriptTarget.Latest,true,ts.ScriptKind.TS)
 const fn=ast.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='entryPageQuery')!
 const source=fn.getText(ast)+';return entryPageQuery()'
 return new Function('session','isChangePage','entryPage',source)({canCorrectBusinessData:corrector},{value:change},{query})
}
describe('entry pending request scope',()=>{
 it.each([false,true])('identifies the exact handling page only for corrector pending (%s)',change=>{
  const query={rowProjection:'active',page:2,sort:'code',direction:'asc',contains:'QA'}
  expect(request(true,change,query)).toEqual({...query,view:'query',handlingView:change?'data_change':'data_entry'})
  expect(request(false,change,query)).toEqual({...query,view:change?'data_change':'data_entry'})
 })
 it.each([false,true])('preserves full query scope for all/concrete states (%s)',change=>{
  for(const status of ['', '报告签发中'])expect(request(true,change,{rowProjection:'',status})).toEqual({rowProjection:'',status,view:'query'})
 })
})
