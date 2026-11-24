import {describe,it,expect,vi} from 'vitest'
import {createListRequestState} from './listRequestState'
describe('Detection list asynchronous state',()=>{
 it('keeps a failed read visible instead of accepting an empty list',async()=>{const s=createListRequestState(),accept=vi.fn();const p=s.run(async()=>{throw Error('网关超时')},accept);expect(s.state.loading).toBe(true);await p;expect(accept).not.toHaveBeenCalled();expect(s.state.loading).toBe(false);expect(s.state.error&&s.state.error.message).toBe('网关超时')})
 it('a previous scope response cannot replace the new scope or clear its loading indicator',async()=>{const s=createListRequestState(),accept=vi.fn();let old!:(v:string[])=>void;const p=s.run(()=>new Promise<string[]>(resolve=>{old=resolve}),accept);await s.run(async()=>['新范围'],accept);old(['旧范围']);await p;expect(accept).toHaveBeenCalledOnce();expect(accept).toHaveBeenCalledWith(['新范围']);expect(s.state.loading).toBe(false)})
 it('unmounted pages ignore pending results',async()=>{const s=createListRequestState(),accept=vi.fn();let resolve!:(v:number)=>void;const p=s.run(()=>new Promise<number>(done=>{resolve=done}),accept);s.dispose();resolve(1);await p;expect(accept).not.toHaveBeenCalled()})
})
