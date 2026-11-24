import type {FormField,FormSchema} from '../../types/forms'
type Row=Record<string,any>
const read=(id:string,label:string,value:unknown):FormField<Row>=>({id,label,control:'text',readonly:true,binding:{get:()=>value==null?'—':String(value)}})
const field=(key:string,label:string,extra:Row={}):FormField<Row>=>({id:'report-'+key,label,control:'text',binding:{get:m=>m[key]??'',set:(m,v)=>{m[key]=v}},...extra})
export function reportSummarySchema(c:Row):FormSchema<Row>{return {sections:(c.visibleSummarySections||[]).map((s:Row,i:number)=>({id:'report-summary-'+i,title:s.title,fields:s.fields.map(([label,value]:any,j:number)=>read(`report-summary-${i}-${j}`,label,value))}))}}
export function reportChecksSchema(c:Row):FormSchema<Row>{return {sections:(c.detail.checks||[]).map((s:Row,i:number)=>({id:'report-check-'+i,title:s.group+' · '+s.status,fields:s.items.map(([label,value]:any,j:number)=>read(`report-check-${i}-${j}`,label,value))}))}}
export function reportTestSchema(c:Row):FormSchema<Row>{return {sections:[{id:'report-test-info',title:'检测数据',fields:[
 field('standard','检测标准'),field('instrument','试验设备'),field('owner','试验员/主检'),
 {id:'report-test-start',label:'开始日期',control:'custom',slot:'start'}, {id:'report-test-end',label:'结束日期',control:'custom',slot:'end'},
 field('resultStatus','结论状态',{control:'select',options:['合格','不合格'].map(value=>({value,label:value}))}),field('unqualifiedParams','不合格参数',{visible:c.testInfo.resultStatus==='不合格'}),
 field('recordNo','记录编号'),field('result','实测值'),field('conclusion','检测结论'),field('remark','备注',{control:'textarea',rows:2}),field('assignedReviewer','指定审核人'),field('assignedApprover','指定批准人'),
 ]}]}}
export function reportOpinionSchema(c:Row):FormSchema<Row>{return {sections:[{id:'report-decision',title:c.pageName+'意见与决定',fields:[
 field('opinion',c.pageName+'意见',{control:'textarea',rows:4,disabled:c.formReadOnly||!c.canActOnSelected,placeholder:'退回时请明确指出需要修改的内容'}),
 read('report-handler','当前处理人',c.session.userName+' · '+c.session.roleName),read('report-scope','报告权限',c.nodeActions.editableScope),read('report-return','退回去向',c.nodeActions.returnTargets.join(' / ')),
 {id:'report-actions',label:'业务操作',control:'custom',slot:'actions'},
 ]}]}}
export function reportVersionSchema(c:Row):FormSchema<Row>{return {sections:[{id:'report-version-state',title:'报告版本状态',fields:[
 read('report-profile','报告模板',c.documentPreflight?.profile.name),read('report-preflight','字段检查',c.documentPreflight?c.documentPreflight.ready?'通过':`缺少 ${c.documentPreflight.missing.length} 项`:'尚未检查'),
 read('report-current-version','流转版本',c.documentVersionsState.currentVersionId),read('report-approved-version','批准版本',c.documentVersionsState.approvedVersionId),read('report-stale','当前版本',c.documentPreflight?.currentVersionStale?'已过期':'未标记过期'),
 ...['主检','审核','批准'].map((key,i)=>read('report-signature-'+i,key,c.signatures[key])),read('report-stamp','电子签章',c.selectedReport?.stamped?c.stampLabel:'未盖章'),
 {id:'report-version-actions',label:'版本操作',control:'custom',slot:'actions'},
 ]}]}}
export function reportTimelineSchema(c:Row):FormSchema<Row>{return {sections:[{id:'report-timeline',title:'当前流程',fields:[read('report-flow-state','数据状态',c.selectedReport?.dataStatus||c.selectedReport?.status),read('report-flow-version','报告版本',c.selectedReport?.version),read('report-flow-scope','本节点操作范围',c.nodeActions.editableScope)]}]}}
export function reportDocumentSchema(c:Row):FormSchema<Row>{return {sections:[
 ...c.editDocument.resultGroups.map((group:Row,i:number)=>({id:'report-edit-group-'+i,title:`检验项目 ${i+1}`,fields:[
 {id:`report-edit-group-name-${i}`,label:'检验项目名称',control:'text',binding:{get:()=>group.name,set:(_:Row,v:string)=>{group.name=v}}},
 ...group.items.flatMap((item:Row,j:number)=>Object.entries({name:'检验项目/参数',condition:'工况/条件',unit:'单位',value:'检验结果'}).map(([key,label])=>({id:`report-edit-${i}-${j}-${key}`,label:`${j+1}. ${label}`,control:'text',binding:{get:()=>item[key]??'',set:(_:Row,v:string)=>{item[key]=v}}}))),
 {id:`report-edit-group-actions-${i}`,label:'项目操作',control:'custom',slot:`group-${i}`},
 ]})),
 {id:'report-edit-remarks',title:'检验结果备注',fields:[field('remarks','备注',{control:'textarea',rows:3})]},
 ...c.editDocument.photos.map((photo:Row,i:number)=>({id:'report-edit-photo-'+i,title:`样品照片 ${i+1}`,fields:[
 {id:`report-edit-photo-file-${i}`,label:'已上传图片',control:'select',emptyLabel:'选择图片',options:c.imageAttachments.map((file:Row)=>({value:String(file.id),label:file.name})),binding:{get:()=>photo.attachmentId==null?'':String(photo.attachmentId),set:(_:Row,v:string)=>{photo.attachmentId=v?Number(v):undefined}}},
 {id:`report-edit-photo-caption-${i}`,label:'图片名称',control:'text',binding:{get:()=>photo.caption,set:(_:Row,v:string)=>{photo.caption=v}}},
 {id:`report-edit-photo-actions-${i}`,label:'照片操作',control:'custom',slot:`photo-${i}`},
 ]})),
 ]} as FormSchema<Row>}
export function reportVersionRows(c:Row):Row[]{return c.documentVersions.map((v:Row)=>({...v,type:v.outputKind==='official'?'正式报告':'内部审核包',state:v.sourceVerification==='unavailable'?'源数据待核实':v.stale?'已过期':'有效',source:v}))}
export const reportVersionColumns=Object.entries({versionLabel:'版本',type:'类型',profileCode:'模板',createdBy:'生成人',createdAt:'生成时间',state:'状态'}).map(([key,label])=>({key,label}))
export function reportFiles(c:Row):{id:string;name:string;type:string;size:number;source:Row}[]{return c.currentAttachments.map((f:Row,i:number)=>({id:String(f.id??i),name:f.name,type:f.contentType||'',size:Number(f.size)||0,source:f}))}
