import {describe,it,expect} from 'vitest'
import {elnDraftSchema,reportPagesSchema} from './entryAuxiliaryForms'
describe('Detection auxiliary SchemaForm bindings',()=>{
 it('selects only reviewed ELN patches and does not write trial values or save',()=>{const c:any={elnDraftPatches:[{path:'result',value:'new'}],elnPatchLabel:()=> '结果',displayDraftValue:String,t:{result:'old'},elnSelectedPatches:[]};const f:any=elnDraftSchema(c).sections[0]!.fields[0];f.binding.set(null,true);expect(c.elnSelectedPatches).toEqual(['result']);expect(c.t.result).toBe('old');f.binding.set(null,false);expect(c.elnSelectedPatches).toEqual([])});
 it('edits page drafts in place with stable per-page field keys and no style configuration',()=>{const pages=[{title:'A',content:'B'}];const s=reportPagesSchema({editPages:pages});const f:any=s.sections[0]!.fields[1];f.binding.set(null,'原文\n第二行');expect(pages[0]!.content).toBe('原文\n第二行');expect(s.sections.flatMap(s=>s.fields).some(f=>Object.keys(f).some(k=>/class|style|font|color/i.test(k)))).toBe(false)});
});
