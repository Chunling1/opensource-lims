import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {defineComponent,reactive,nextTick} from 'vue'
import {mount} from '@vue/test-utils'
vi.mock('@/services/pipeline',()=>({fetchCompliancePreflight:vi.fn()}))
import {fetchCompliancePreflight} from '@/services/pipeline'
import {createContractReviewPresentation} from './contractReviewPresentation'
const wrappers:any[]=[]
afterEach(()=>wrappers.splice(0).forEach(w=>w.unmount()))
beforeEach(()=>{vi.mocked(fetchCompliancePreflight).mockResolvedValue({ready:true,preflightVersion:'v1',issues:[],hardBlockers:[],requiresOpinion:false} as any)})
function setup(){const c=reactive<any>({form:{items:{tech:false,instrument:false,env:false,method:false,personnel:false,sample:false,basisAuth:false},cma:false,cnas:false,opinion:''},formOpen:true,formReadOnly:false,reviewBusy:false,reviewDetailLoading:false,selectedReport:{reportNo:'R1'},canPass:true,session:{canAction:()=>true},approve:vi.fn(),submit:vi.fn(async()=>{c.formOpen=false})});let p:any;wrappers.push(mount(defineComponent({setup(){p=createContractReviewPresentation(c);return()=>null}})));return {c,p}}
describe('template contract review adapter',()=>{
 it('does not inherit checked demo defaults and maps all seven decisions',()=>{const {c,p}=setup();expect(p.form.technicalCapability).toBe(false);p.form.technicalCapability=true;p.form.basisAuthorization=true;expect(c.form.items.tech).toBe(true);expect(c.form.items.basisAuth).toBe(true);p.form.other=true;expect(p.form.other).toBe(false)})
 it('requires current compliance result and explicit read confirmation',async()=>{const {c,p}=setup();expect(p.canApprove).toBe(false);await p.check();expect(p.canApprove).toBe(false);p.readConfirmed=true;expect(p.canApprove).toBe(true);c.form.items.tech=true;await nextTick();expect(p.canApprove).toBe(false)})
 it('blocks hard errors and requests opinion only when required',async()=>{const {p}=setup();vi.mocked(fetchCompliancePreflight).mockResolvedValue({ready:true,preflightVersion:'v2',issues:[],hardBlockers:[],requiresOpinion:true} as any);await p.check();p.readConfirmed=true;expect(p.requiresOpinion).toBe(true);expect(p.canApprove).toBe(false);p.opinion.value='已核对';expect(p.canApprove).toBe(true);vi.mocked(fetchCompliancePreflight).mockResolvedValue({ready:false,preflightVersion:'v3',issues:[],hardBlockers:['阻塞'],requiresOpinion:false} as any);await p.check();p.readConfirmed=true;expect(p.canApprove).toBe(false)})
 it('preserves rejection reason and denies empty / read-only returns',async()=>{const {c,p}=setup();expect(await p.reject(' ')).toBe(false);expect(c.submit).not.toHaveBeenCalled();c.formReadOnly=true;await p.reject('原因');expect(c.submit).not.toHaveBeenCalled();c.formReadOnly=false;await p.reject(' 请补充记录 ');expect(c.form.opinion).toBe('请补充记录');expect(c.submit).toHaveBeenCalledWith('return')})
 it('ignores preflight resolved after changing selected report',async()=>{let resolve:any;vi.mocked(fetchCompliancePreflight).mockImplementation(()=>new Promise(r=>resolve=r));const {c,p}=setup();const pending=p.check();c.selectedReport={reportNo:'R2'};resolve({ready:true,issues:[],hardBlockers:[]});await pending;expect(p.hasResults).toBe(false)})
})
