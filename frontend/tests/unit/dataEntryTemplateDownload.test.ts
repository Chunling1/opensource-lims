import { expect, test } from 'vitest'
import { templateTask } from '../../server/dataEntryTasks'
import type { EntryTemplateJob } from '../../src/types/testing/dataEntryDetail'

const job: EntryTemplateJob = { id: 'word-only', sourceKey: 'saved-snapshot', sourceRevision: 1, layoutId: 'standard', templateVersion: '2', createdAt: 1000, stage: 'word', wordAvailable: false, pdfAvailable: false, elapsedMs: 0, wordOnly: true }

test('download-only tasks finish at Word generation and never expose a PDF result', () => {
  expect(templateTask(job, 1500)).toMatchObject({ stage: 'word', wordAvailable: false, pdfAvailable: false })
  expect(templateTask(job, 1800)).toMatchObject({ stage: 'ready', wordAvailable: true, pdfAvailable: false, elapsedMs: 800 })
  expect(templateTask(job, 100000)).toMatchObject({ stage: 'ready', pdfAvailable: false, elapsedMs: 800 })
})

test('download-only failure and slow scenarios apply to Word, not conversion', () => {
  expect(templateTask({ ...job, scenario: 'word-failure' }, 1800)).toMatchObject({ stage: 'word-failed', wordAvailable: false, pdfAvailable: false })
  expect(templateTask({ ...job, scenario: 'slow' }, 2000)).toMatchObject({ stage: 'word', wordAvailable: false })
  expect(templateTask({ ...job, scenario: 'slow' }, 46000)).toMatchObject({ stage: 'ready', wordAvailable: true, pdfAvailable: false })
  expect(templateTask({ ...job, wordOnly: undefined }, 100000)).toMatchObject({ stage: 'ready', pdfAvailable: true })
})
