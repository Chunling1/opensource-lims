import type {FormSchema} from '../../types/forms'
export interface ReviewForm {items:Record<string,boolean>;cma:boolean;cnas:boolean;opinion:string}
export function reviewFormSchema(c:{idPrefix:string;crItems:{key:string;name:string}[];checkedCount:number;requiredCma:boolean;requiredCnas:boolean;reviewDetailLoading:boolean}):FormSchema<ReviewForm>{return {sections:[
{id:'review-requirements',title:'合同评审确认（'+c.checkedCount+'/7 已确认）',fields:c.crItems.map(it=>({id:c.idPrefix+'-'+it.key,label:it.name,control:'checkbox',binding:{get:m=>!!m.items[it.key],set:(m,v)=>{m.items[it.key]=v}}}))},
{id:'review-seals',title:'委托盖章要求：'+([c.requiredCma?'CMA':'',c.requiredCnas?'CNAS':''].filter(Boolean).join('、')||'未要求 CMA/CNAS'),fields:([{key:'cma',label:'确认 CMA 要求及授权范围',required:c.requiredCma},{key:'cnas',label:'确认 CNAS 要求及授权范围',required:c.requiredCnas}] as const).map(it=>({id:c.idPrefix+'-'+it.key,label:it.label,control:'checkbox',disabled:c.reviewDetailLoading||!it.required,binding:{get:m=>m[it.key],set:(m,v)=>{m[it.key]=v}}}))},
{id:'review-opinion',title:'评审意见',fields:[{id:c.idPrefix+'-opinion-text',label:'意见 / 退回原因',control:'textarea',rows:3,width:'col-12',placeholder:'退回需填写不通过原因',binding:{get:m=>m.opinion,set:(m,v)=>{m.opinion=v}}}]}
]}}
