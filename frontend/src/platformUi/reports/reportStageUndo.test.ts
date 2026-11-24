import {describe, it, expect, vi} from 'vitest'
import {reactive} from 'vue'
import {createReportStageUndo, type ReportReviewStage} from './reportStageUndo'
import {createReportStagePresentation} from './reportStagePresentation'

function setup(stage:ReportReviewStage='review') {
  const action=`report.${stage}.undo`
  const c=reactive<any>({pageKey:stage,pageName:stage==='review'?'报告审核':'报告批准',
    workRows:[{reportNo:'LAB-TEST-001',sampleNo:'TEST-001',status:stage==='review'?'待批准':'待打印',
      allowedActions:[action],rowProjection:'recall'}],
    session:{canAction:vi.fn(()=>true)},openForm:vi.fn(),refreshReportList:vi.fn(async()=>{})})
  const perform=vi.fn(async()=>({reportNo:'LAB-TEST-001',status:stage==='review'?'待审核':'待批准'}))
  const invalidate=vi.fn()
  c.undoReport=createReportStageUndo({page:()=>c.pageKey,rows:()=>c.workRows,
    canAction:a=>c.session.canAction(a),perform,invalidate,refresh:c.refreshReportList})
  const m=createReportStagePresentation(c)
  m.rowAction(m.rows.items[0],stage==='review'?'撤销审核':'撤销批准')
  return {c,m,perform,invalidate,action}
}

describe('report list recall through the real workflow adapter',()=>{
  it.each(['review','approval'] as const)('%s confirmation calls workflow and refreshes the same report',async stage=>{
    const {m,c,perform,invalidate,action}=setup(stage)
    expect(m.statusAction).toBeTruthy()
    await m.undoCheck()
    expect(perform).toHaveBeenCalledExactlyOnceWith('LAB-TEST-001',action)
    expect(invalidate).toHaveBeenCalledExactlyOnceWith('LAB-TEST-001')
    expect(c.refreshReportList).toHaveBeenCalledTimes(1)
    expect(m.statusAction).toBeUndefined()
    expect(m.actionBusy).toBe(false)
    expect(c.openForm).not.toHaveBeenCalled()
  })
  it.each(['permission','rowPermission','status','removed'] as const)('rechecks %s after opening confirmation',async change=>{
    const {m,c,perform}=setup()
    if(change==='permission')c.session.canAction.mockReturnValue(false)
    if(change==='rowPermission')c.workRows[0].allowedActions=[]
    if(change==='status')c.workRows[0].status='待打印'
    if(change==='removed')c.workRows=[]
    await m.undoCheck()
    expect(perform).not.toHaveBeenCalled()
    expect(m.statusError.message).toContain('状态或撤销权限已变化')
  })
  it('shows server rejection without success or clearing cached detail',async()=>{
    const {m,c,perform,invalidate}=setup()
    perform.mockRejectedValue(new Error('该报告已进入下个流程'))
    await m.undoCheck()
    expect(m.statusError.message).toBe('该报告已进入下个流程')
    expect(m.statusAction).toBeTruthy()
    expect(c.refreshReportList).not.toHaveBeenCalled()
    expect(invalidate).not.toHaveBeenCalled()
  })
  it('does not treat an empty service response as success',async()=>{
    const {m,perform,invalidate}=setup()
    perform.mockResolvedValue(null as any)
    await m.undoCheck()
    expect(m.statusError.message).toContain('撤销未完成')
    expect(invalidate).not.toHaveBeenCalled()
  })
  it('submits once during repeated confirmation',async()=>{
    const {m,perform}=setup()
    let done!:(value:any)=>void
    perform.mockImplementation(()=>new Promise(resolve=>{done=resolve}))
    const first=m.undoCheck()
    await m.undoCheck()
    expect(perform).toHaveBeenCalledTimes(1)
    done({reportNo:'LAB-TEST-001',status:'待审核'})
    await first
    expect(m.actionBusy).toBe(false)
  })
  it.each([true,false])('ignores a late result after switching pages (success=%s)',async success=>{
    const {m,c,perform}=setup()
    let done!:(value:any)=>void,fail!:(value:any)=>void
    perform.mockImplementation(()=>new Promise((resolve,reject)=>{done=resolve;fail=reject}))
    const pending=m.undoCheck()
    c.pageKey='approval'
    expect(m.statusAction).toBeUndefined()
    if(success)done({reportNo:'LAB-TEST-001',status:'待审核'});else fail(new Error('late failure'))
    await pending
    expect(m.statusError).toBe('')
    expect(c.refreshReportList).not.toHaveBeenCalled()
  })
})
