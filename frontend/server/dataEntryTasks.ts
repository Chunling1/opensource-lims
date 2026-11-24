import type { EntryJob, EntryTemplateJob } from '../src/types/testing/dataEntryDetail'

// Session-persisted mock tasks advance by server time, independently of page polling.
export function templateTask(job: EntryTemplateJob, now: number): EntryTemplateJob {
  const elapsed = Math.max(0, now - job.createdAt), conversionElapsed = Math.max(0, now - (job.conversionStartedAt ?? job.createdAt + 800))
  const queue = job.scenario === 'slow' ? 45000 : 1200
  if (job.wordOnly) {
    const duration = job.scenario === 'slow' ? 45000 : 800
    const stage = elapsed < duration ? 'word' : ['failure', 'word-failure'].includes(job.scenario || '') ? 'word-failed' : 'ready'
    return { ...job, stage, wordAvailable: stage === 'ready', pdfAvailable: false, elapsedMs: Math.min(elapsed, duration), error: stage === 'word-failed' ? '模拟 Word 生成失败，请重试下载模板。' : undefined }
  }
  const stage = !job.conversionStartedAt && elapsed < 800 ? 'word'
    : job.scenario === 'word-failure' ? 'word-failed'
    : conversionElapsed < queue ? 'queued'
    : conversionElapsed < queue + 1200 ? 'converting'
    : job.scenario === 'pdf-failure' || job.scenario === 'failure' ? 'pdf-failed' : 'ready'
  const end = stage === 'word-failed' ? 800 : (job.conversionStartedAt ? job.conversionStartedAt - job.createdAt : 800) + queue + 1200
  return { ...job, stage, wordAvailable: !['word', 'word-failed'].includes(stage), pdfAvailable: stage === 'ready', elapsedMs: Math.min(elapsed, end),
    error: stage === 'word-failed' ? '模拟 Word 生成失败，请重试生成模板。' : stage === 'pdf-failed' ? '模拟 PDF 转换失败，Word 已保留，可下载或重试预览转换。' : undefined }
}
export function finalTask(job: EntryJob, now: number, fileIds: string[]): EntryJob {
  const duration = job.scenario === 'slow' ? 45000 : 1200, elapsed = Math.max(0, now - job.createdAt)
  const status = elapsed < duration ? 'running' : job.scenario === 'failure' ? 'failed' : 'ready'
  const phase = status !== 'running' ? status : elapsed < duration / 4 ? 'queued' : elapsed < duration / 2 ? 'preparing' : elapsed < duration * 3 / 4 ? 'converting' : 'composing'
  const stages = { queued: '等待后台处理', preparing: '准备报告资料', converting: '转换报告文件', composing: '编排报告、背景与页码', ready: '完整报告已生成', failed: '生成失败' }
  return { ...job, status, phase, stage: stages[phase], elapsedMs: Math.min(elapsed, duration),
    error: status === 'failed' ? '模拟报告生成失败，文件已保留，请重试。' : undefined,
    fileErrors: status === 'failed' ? Object.fromEntries(fileIds.map(id => [id, '模拟文件转换失败'])) : {} }
}
