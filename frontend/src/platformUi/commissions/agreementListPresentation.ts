import { toRef } from 'vue'
import { persistTableSettings } from '../../services/platform/tablePreferences'
import {computed,reactive,ref,watch} from 'vue'
import {contractRowKey} from '@/services/contractScope'
import keys from './AgreementListPresentation.keys.json'
import {AppError} from '../../services/common/errors'
import {exportRowsXlsx} from '@/services/xlsxExport'
type Row=Record<string,any>
export function createAgreementListPresentation(c:Row){const m=reactive<Row>(Object.fromEntries(keys.map(k=>[k,undefined]))),selected=ref<string[]>([]),modal=ref<Row>(),draft=reactive({keyword:c.keyword,status:c.statusFilter,from:'',to:''}),chosen=ref<string[]>([]);
 const cols=Object.entries({erpProjectNo:'外部ERP项目编号',erpProjectType:'外部ERP项目类型',projectAuditTime:'项目审核时间',contractStartDate:'合同开始日期',erpLogReceivedAt:'外部ERP接收时间',projectName:'项目名称',client:'客户名称',businessDepartment:'业务所属部门',projectOwner:'项目负责人',registrar:'登记人',testDepartment:'项目部门（检测部门）',registeredAt:'登记时间',remark:'备注',registrationStatus:'合同登记状态'}).map(([key,label])=>({key,label,required:key==='erpProjectNo',truncate:['projectName','client'].includes(key)?24:undefined,fullTitle:true}));
 persistTableSettings(()=> 'agreement',{columns:chosen,pageSize:toRef(c,'pageSize')});
 const canWrite=computed(()=>(c.session.canCorrectBusinessData||c.session.can('entrust.agreement.view'))&&!c.session.businessReadOnly),select=(ids:string[])=>c.onProjectSelectionChange(c.projectRows.filter((r:Row)=>ids.includes(contractRowKey(r as any))));
 watch(selected,select,{flush:'sync'});watch(()=>c.projectRows,()=>selected.value=[]);
 const canCreate=computed(()=>!!c.session.canCorrectBusinessData&&!c.session.businessReadOnly);
 const canDelete=(_row:Row)=>c.session.canAction('entrust.agreement.delete')&&!c.session.businessReadOnly;
 watch(modal,v=>{if(!v)return;modal.value=undefined;if(v.mode==='new'){if(canCreate.value)c.startNew();return}selected.value=[v.row.id];if(v.mode==='view')c.openSelectedProject();else if(v.mode==='edit'&&canWrite.value)c.modifySelectedProject();else if(v.mode==='delete'&&c.canDeleteSelected&&!c.session.businessReadOnly)void c.deleteSelectedClaims()},{flush:'sync'});
 const actions=computed(()=>[{label:'外部ERP内容管理',icon:'ti ti-edit',key:'admin',disabled:!c.session.canCorrectBusinessData||c.session.businessReadOnly},{label:'修改',icon:'ti ti-edit',key:'edit',disabled:!canWrite.value||selected.value.length!==1},{label:'撤销登记',icon:'ti ti-arrow-back-up',key:'undo',disabled:!canWrite.value||selected.value.length!==1||c.selectedProject?.agreement?.status!=='已登记'},{label:'查看',icon:'ti ti-eye',key:'view',disabled:selected.value.length!==1},{label:'删除',icon:'ti ti-trash',key:'delete',disabled:!c.canDeleteSelected||c.session.businessReadOnly}]);
 Object.assign(m,{canWrite,canCreate,canDelete,selected,modal,loading:computed(()=>c.listLoading),error:computed(()=>c.listError?new AppError('NETWORK',c.listError):''),exportError:'',exporting:false,message:'',importing:false,draft,fields:[{key:'keyword',label:'合同/项目编号 / 项目名称 / 客户名称'},{key:'status',label:'合同登记状态',placeholder:'合同登记中 / 已登记'},{key:'from',label:'登记开始日期',type:'date'},{key:'to',label:'登记结束日期',type:'date'}],
 data:computed(()=>({items:c.paged.map((r:Row)=>({...r,id:contractRowKey(r as any),name:r.projectName,code:r.erpProjectNo,source:r})),total:c.serverPaging?c.workspaceTotal:c.filtered.length,page:c.tablePage,pageSize:c.pageSize})),projectColumns:cols,columnKeys:computed(()=>chosen.value.length?chosen.value:cols.map(x=>x.key)),columns:computed(()=>cols.filter(x=>!chosen.value.length||chosen.value.includes(x.key))),toolbarActions:actions,
 toolbarAction:(i:number)=>{const a=actions.value[i];if(!a||a.disabled)return;if(a.key==='admin'){window.location.hash='/inspection/quality/erp_content';return}({edit:c.modifySelectedProject,undo:c.undoSelectedProject,view:c.openSelectedProject,delete:c.deleteSelectedClaims} as Row)[a.key]?.()},
 search:()=>{c.keyword=draft.keyword;c.statusFilter=draft.status;c.registrationDateRange=draft.from||draft.to?[draft.from,draft.to]:null;c.tablePage=1},load:c.load,patch:(v:Row)=>{if('columns'in v)chosen.value=[];if(v.size)c.pageSize=Number(v.size);c.tablePage=Number(v.page)||1},toggleColumn:(key:string,on:boolean)=>{const old=chosen.value.length?chosen.value:cols.map(x=>x.key);chosen.value=on?[...new Set([...old,key])]:old.filter(k=>k!==key)},
 exportRows:(onlySelected:boolean)=>onlySelected?exportRowsXlsx('合同项目',cols.map(x=>({...x,width:20})),c.projectRows.filter((r:Row)=>selected.value.includes(contractRowKey(r as any)))):c.exportErpList(),
 });return m as any}
