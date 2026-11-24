import type {FormSchema} from '../../types/forms'
type Context=Record<string,any>
export function elnDraftSchema(c:Context):FormSchema<any>{return {sections:[{id:'eln-reviewed-draft',title:'选择导入字段',fields:c.elnDraftPatches.map((p:Context,i:number)=>({id:'eln-reviewed-field-'+i,label:c.elnPatchLabel(p.path),control:'checkbox',hint:`${c.displayDraftValue(c.t[p.path])} → ${c.displayDraftValue(p.value)}`,binding:{get:()=>c.elnSelectedPatches.includes(p.path),set:(_:unknown,v:boolean)=>{c.elnSelectedPatches=v?[...new Set([...c.elnSelectedPatches,p.path])]:c.elnSelectedPatches.filter((key:string)=>key!==p.path)}}}))}]}}
export function reportPagesSchema(c:Context):FormSchema<any>{return {sections:c.editPages.map((p:Context,i:number)=>({id:'report-addendum-'+i,title:`报告附加页 ${i+1}`,fields:[
 {id:'report-addendum-title-'+i,label:'页标题',control:'text',binding:{get:()=>p.title,set:(_:unknown,v:string)=>{p.title=v}}},
 {id:'report-addendum-content-'+i,label:'正文内容',control:'textarea',rows:3,binding:{get:()=>p.content,set:(_:unknown,v:string)=>{p.content=v}}},
 {id:'report-addendum-remove-'+i,label:'操作',control:'custom',slot:'remove-page-'+i},
 ]}))}}
