import {describe,it,expect} from 'vitest'
import {mount} from '@vue/test-utils'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import {reviewFormSchema, type ReviewForm} from './reviewForm'
const items=['tech','instrument','env','method','personnel','sample','basisAuth'].map(key=>({key,name:key}))
const schema=()=>reviewFormSchema({idPrefix:'review',crItems:items,checkedCount:0,requiredCma:true,requiredCnas:false,reviewDetailLoading:false})
describe('Contract review uses the original form model',()=>{
 it('writes each of seven requirements and the opinion to the retained model',async()=>{
 const model:ReviewForm={items:{},cma:false,cnas:false,opinion:''}
 const view=mount(SchemaForm<ReviewForm>,{props:{schema:schema(),model},slots:{requirements:'',seals:''}})
 for(const item of items)await view.get('#review-'+item.key).setValue(true)
 await view.get('#review-cma').setValue(true)
 await view.get('#review-opinion-text').setValue('需要补充依据')
 expect(model.items).toEqual(Object.fromEntries(items.map(i=>[i.key,true])))
 expect(model.cma).toBe(true);expect(model.opinion).toBe('需要补充依据')
 expect(view.get('#review-cnas').attributes('disabled')).toBeDefined()
 })
 it('locks every field in read-only mode',()=>{
 const model:ReviewForm={items:{tech:true},cma:false,cnas:false,opinion:'已审'}
 const view=mount(SchemaForm<ReviewForm>,{props:{schema:schema(),model,readonly:true},slots:{requirements:'',seals:''}})
 expect(view.findAll('input').every(n=>n.attributes('disabled')!==undefined)).toBe(true)
 expect(view.get('textarea').attributes('readonly')).toBeDefined()
 })
})
