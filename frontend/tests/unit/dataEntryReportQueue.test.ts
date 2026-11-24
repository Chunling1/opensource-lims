import { expect, it } from 'vitest'
import { finalTask } from '../../server/dataEntryTasks'
import type { EntryJob } from '../../src/types/testing/dataEntryDetail'

it('reports queue and processing phases from the same task until the result is ready', () => {
  const job: EntryJob = { id: 'queued-report', sourceRevision: 1, sourceKey: 'sample', templateKey: 'standard', createdAt: 10000, status: 'running', scenario: 'slow' }
  for (const [elapsed, phase] of [[0, 'queued'], [12000, 'preparing'], [24000, 'converting'], [36000, 'composing'], [45000, 'ready']] as const) {
    const result = finalTask(job, job.createdAt + elapsed, [])
    expect(result.id).toBe(job.id)
    expect(result.phase).toBe(phase)
    expect(result.status).toBe(phase === 'ready' ? 'ready' : 'running')
    expect(result.elapsedMs).toBe(elapsed)
  }
})

it('reports conversion failure without discarding task or file errors', () => {
  const job: EntryJob = { id: 'failed-report', sourceRevision: 1, sourceKey: 'sample', templateKey: 'standard', createdAt: 10000, status: 'running', scenario: 'failure' }
  expect(finalTask(job, 10000, ['file-1']).phase).toBe('queued')
  const result = finalTask(job, 13000, ['file-1'])
  expect(result.status).toBe('failed')
  expect(result.phase).toBe('failed')
  expect(result.fileErrors?.['file-1']).toBeTruthy()
})
