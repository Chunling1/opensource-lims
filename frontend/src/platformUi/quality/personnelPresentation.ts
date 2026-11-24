import { toRef } from 'vue'
import { persistTableSettings } from '../../services/platform/tablePreferences'
import {computed,reactive,ref,watch} from 'vue'
import keys from './PersonnelPresentation.keys.json'
import type {FormSchema} from '../../types/forms'
type Row=Record<string,any>
export function personnelSchema(c:Row):FormSchema<any>{
 const text=(key:string,label:string,extra:Row={})=>({id:'platform-personnel-'+key,label,control:'text' as const,binding:{get:(m:Row)=>m[key]??'',set:(m:Row,v:string)=>{m[key]=v}},...extra});
 return {sections:[{id:'personnel-profile',title:'人员档案',fields:[
 text('name','姓名',{required:true,maxlength:40}),text('code','人员编号',{required:true,maxlength:40,hint:'保存未关联账号的人员时同步建立登录账号；正式权限在组织机构配置。',disabled:!!c.form?.linkedUserId}),text('gender','性别'),
 c.canManageAccounts?{id:'platform-personnel-department',label:'所在部门',control:'select',emptyLabel:'请选择部门',options:c.deptOptions.map((d:Row)=>({value:String(d.id??''),label:d.name,disabled:d.id==null})),binding:{get:(m:Row)=>m.departmentId==null?'':String(m.departmentId),set:(m:Row,v:string)=>{m.departmentId=v?Number(v):null;c.syncDepartmentName(m.departmentId)}}}:text('dept','所在部门'),
 text('roleName','岗位/角色',{maxlength:30}),text('title','职称/资格'),
 text('mobile','名册手机号',{control:'tel',maxlength:11,visible:!!c.canSensitive,hint:'电子签署以此号码为准。修改后请先保存人员档案。'}),
 {id:'platform-personnel-approval',label:'审批职位',control:'select',emptyLabel:'未设置',options:[{value:'department_director',label:'部门主任'},{value:'institute_leader',label:'院领导'}],hint:'仅用于更正申请审批；不授予功能菜单或项目权限。',binding:{get:(m:Row)=>m.approvalPosition||'',set:(m:Row,v:string)=>{m.approvalPosition=v}}},
 {id:'platform-personnel-enabled',label:'账号启用',control:'checkbox',visible:!!c.form?.linkedUserId&&c.canManageAccounts,binding:{get:(m:Row)=>!!m.accountEnabled,set:(m:Row,v:boolean)=>{m.accountEnabled=v}}},
 text('education','文化程度'),text('major','所学专业'),text('school','毕业院校'),text('idNo','身份证号',{disabled:!c.canSensitive,hint:!c.canSensitive?'需要敏感信息查看权限':undefined}),
 text('workStartTime','参加工作时间',{control:'date'}),text('joinTime','来单位时间',{control:'date'}),text('remark','备注',{control:'textarea',rows:2}),
 ]}]}
}
export function createPersonnelPresentation(c:Row){
 const context=reactive<Row>(Object.fromEntries(keys.map(k=>[k,undefined]))),selected=ref<string[]>([]),modal=ref<Row>(),draft=reactive({keyword:c.kw,department:c.deptFilter}),chosen=ref(['name','code','department','position','qualification','accountStatus','permissions']);
 persistTableSettings(()=> 'personnel',{columns:chosen,pageSize:toRef(c,'size')});
 const columns=[{key:'name',label:'姓名',required:true},{key:'code',label:'人员编号/账号'},{key:'department',label:'所在部门'},{key:'position',label:'岗位/职务'},{key:'qualification',label:'职称/资格'},{key:'accountStatus',label:'账号状态'},{key:'permissions',label:'流程权限',wrap:true}];
 watch(modal,value=>{if(!value)return;modal.value=undefined;c.personnelViewOnly=value.mode==='view';if(value.mode==='new')c.openCreate();else if(value.mode==='delete')void c.confirmRemove(value.record.source);else void c.openEdit(value.record.source)},{flush:'sync'});
 Object.assign(context,{
 canCreate:computed(()=>c.session.canAction('quality.personnel.create')),canUpdate:computed(()=>c.session.canAction('quality.personnel.update')),canDelete:computed(()=>c.session.canAction('quality.personnel.delete')),title:'人员登记',queryMode:false,queryLabel:'人员查询',draft,selected,modal,canWrite:computed(()=>c.session.canAction('quality.personnel.create')||c.session.canAction('quality.personnel.update')),loading:computed(()=>c.loading),exporting:computed(()=>c.exporting),error:'',actionError:'',message:'',importing:false,
 primaryFields:computed(()=>[{key:'keyword',label:'姓名 / 编号 / 部门'},{key:'department',label:'部门',options:c.deptOptions.map((r:Row)=>r.name)}]),extraFields:[],more:false,activeFilters:0,
 rows:computed(()=>({items:c.rows.map((r:Row)=>({...r,id:String(r.id),department:r.dept,qualification:r.title,permissions:(r.permissions||[]).join('、'),source:r})),total:c.total,page:c.page,pageSize:c.size})),query:{},personnelColumns:columns,columnKeys:chosen,columns:computed(()=>columns.filter(x=>chosen.value.includes(x.key))),
 search:()=>{c.kw=draft.keyword;c.deptFilter=draft.department;void c.reload(1)},load:()=>c.reload(c.page),
 patch:(v:Row)=>{if('columns'in v)chosen.value=columns.map(x=>x.key);if(v.size)c.size=Number(v.size);void c.reload(Number(v.page)||1)},
 toggleColumn:(key:string,checked:boolean)=>chosen.value=checked?[...new Set([...chosen.value,key])]:chosen.value.filter(k=>k!==key),
 toolbarActions:computed(()=>[{label:'下载导入模板',icon:'ti ti-download',disabled:!c.canImport},{label:'导入人员',icon:'ti ti-upload',disabled:!c.canImport},{label:'全员电子签署绑定',icon:'ti ti-link',disabled:!c.canManageEsign}]),
 toolbarAction:(i:number)=>{if(i===0&&c.canImport)void c.downloadPersonnelTemplate();if(i===1&&c.canImport)c.openImport();if(i===2&&c.canManageEsign)c.bindingRosterOpen=true},download:()=>c.handleExport(),saved:()=>c.reload(c.page),
 });return context as any
}

export function esignSchema(c:Row):FormSchema<Row>{return {sections:[{id:'personnel-esign',title:'电子签署身份',fields:[
 {id:'esign-name',label:'签署姓名',control:'text',maxlength:40,binding:{get:m=>m.esignLegalName,set:(m,v)=>{m.esignLegalName=v}}},
 {id:'esign-phone',label:'签署绑定手机号',control:'tel',maxlength:11,placeholder:c.placeholder||'与名册手机号一致',hint:'只修改人员资料时留空。要绑定，请先保存名册手机号，再点“使用名册手机号绑定”；首次实名由本人完成。',binding:{get:m=>m.esignAccountInput,set:(m,v)=>{m.esignAccountInput=v}}},
 {id:'esign-status',label:'绑定状态',control:'text',readonly:true,binding:{get:m=>m.esignBindingStatus}},
 {id:'esign-binding',label:'绑定操作',control:'custom',slot:'binding'},
 ]}]}}
