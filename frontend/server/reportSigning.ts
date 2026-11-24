import { createHash, timingSafeEqual } from 'node:crypto'
import { PDFDocument, StandardFonts, rgb } from 'pdf-lib'
import type { FrozenReportFile, ReportRelease } from '../src/types/reports/reportLifecycle'

export interface SigningResult {
  externalId: string; status: 'running' | 'unknown' | 'failed' | 'complete'; signature: boolean; seal: boolean; file?: FrozenReportFile; error?: string
}
export interface SigningProvider {
  name: string
  submit(release: ReportRelease): Promise<SigningResult>
  query(release: ReportRelease): Promise<SigningResult>
  verifyCallback(token: string): boolean
}
export function reportFile(bytes: Uint8Array, id: string, name: string): FrozenReportFile {
  return { id, name, base64: Buffer.from(bytes).toString('base64'), sha256: createHash('sha256').update(bytes).digest('hex') }
}
export async function demoSignedReport(release: ReportRelease): Promise<FrozenReportFile> {
  const pdf = await PDFDocument.load(Buffer.from(release.original.base64, 'base64')), font = await pdf.embedFont(StandardFonts.Helvetica)
  pdf.getPages()[0]!.drawText('DEMO ONLY - electronic signing simulation', { x: 35, y: 24, size: 10, font, color: rgb(0.65, 0, 0) })
  return reportFile(await pdf.save(), `${release.id}-signed`, release.original.name)
}
// Explicit demo adapter. The generated marker is not a cryptographic signature or an official seal.
// Production adapters must retain idempotency keys, query unknown submissions and verify vendor callbacks.
export function createDemoSigningProvider(secret: string, scenario: 'success' | 'failure' | 'timeout' = 'success'): SigningProvider {
  const tasks = new Map<string, { createdAt: number; result?: SigningResult; release: ReportRelease }>()
  async function result(release: ReportRelease): Promise<SigningResult> {
    const task = tasks.get(release.signing!.key), externalId = `demo-${release.signing!.key}`
    if (!task) return { externalId, status: 'unknown', signature: false, seal: false, error: '服务商任务尚未确认，等待核对原任务。' }
    if (task.result) return task.result
    if (Date.now() - task.createdAt < 1200) return { externalId, status: 'running', signature: false, seal: false }
    if (scenario === 'failure') return { externalId, status: 'failed', signature: false, seal: false, error: '演示签章服务失败，可重试。' }
    task.result = { externalId, status: 'complete', signature: true, seal: true, file: await demoSignedReport(task.release) }
    return task.result
  }
  return {
    name: 'demo',
    async submit(release) {
      const key = release.signing!.key
      if (!tasks.has(key)) tasks.set(key, { createdAt: Date.now(), release: structuredClone(release) })
      if (scenario === 'timeout') return { externalId: `demo-${key}`, status: 'unknown', signature: false, seal: false, error: '提交超时，正在查询原任务。' }
      return result(release)
    },
    query: result,
    verifyCallback(token) {
      const received = Buffer.from(token), expected = Buffer.from(secret)
      return expected.length >= 32 && received.length === expected.length && timingSafeEqual(received, expected)
    },
  }
}
