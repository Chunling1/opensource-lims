import {afterEach, beforeEach, expect, it, vi} from 'vitest'
const mocks=vi.hoisted(()=>({request:vi.fn(),state:vi.fn()}))
vi.mock('@/services/http',async original=>({...await original<typeof import('@/services/http')>(),request:mocks.request}))
vi.mock('@/services/auth',()=>({USE_BACKEND:true}))
vi.mock('@/services/attachments',()=>({completePreviewState:mocks.state}))
import {changeTestComplete, completeTestInfo, TestCompletionUncertain} from '@/services/pipeline'
import {ApiError} from '@/services/http'
import {AppError} from '../services/common/errors'
beforeEach(()=>{vi.useFakeTimers();vi.clearAllMocks();mocks.request.mockResolvedValue({status:'待审核'})})
afterEach(()=>vi.useRealTimers())
it('requires opening the latest preview rather than generating on submission',async()=>{
  mocks.state.mockResolvedValue({status:'queued'})
  await expect(changeTestComplete('TEST-1')).rejects.toThrow('报告确认')
  expect(mocks.state).toHaveBeenCalledExactlyOnceWith('TEST-1','data_change')
  expect(mocks.request).not.toHaveBeenCalled()
})
it('does not advance workflow when generation fails',async()=>{
  mocks.state.mockResolvedValue({status:'failed',message:'转换失败'})
  await expect(changeTestComplete('TEST-1')).rejects.toThrow('报告确认')
  expect(mocks.request).not.toHaveBeenCalled()
})
it('reuses an already ready PDF without polling',async()=>{
  mocks.state.mockResolvedValue({status:'ready'})
  await changeTestComplete('TEST-1')
  expect(mocks.state).toHaveBeenCalledOnce();expect(mocks.request).toHaveBeenCalledOnce()
})
it.each([new AppError('NETWORK','timeout'), new ApiError('gateway',504)])('identifies an uncertain POST once',async error=>{
  mocks.request.mockRejectedValueOnce(error)
  await expect(completeTestInfo('TEST-1')).rejects.toBeInstanceOf(TestCompletionUncertain)
  expect(mocks.request).toHaveBeenCalledOnce()
})
it('preserves a business rejection and distinguishes a preview check failure',async()=>{
  const rejected=new ApiError('请先确认最新报告',200,1)
  mocks.request.mockRejectedValueOnce(rejected)
  await expect(completeTestInfo('TEST-1')).rejects.toBe(rejected)
  const network=new AppError('NETWORK','timeout')
  mocks.state.mockRejectedValueOnce(network)
  await expect(changeTestComplete('TEST-1')).rejects.toBe(network)
  expect(mocks.request).toHaveBeenCalledOnce()
})
