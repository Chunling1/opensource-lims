import { randomUUID } from 'node:crypto'
import { resolve } from 'node:path'
import PdfPrinter from 'pdfmake'
import type { Content } from 'pdfmake/interfaces'
import { AppError } from '../src/services/common/errors'
import { copyNames, printDescription, type PrintTask, type PrintScenario, type PrintContext } from '../src/types/commissions/commissionPrint'

export interface PrintSource extends PrintContext { preview: { customer: string; contact: string; phone: string; projects: string[] } }
interface StoredTask { task: PrintTask; snapshot: PrintSource; scenario: PrintScenario }
// Mock queue survives navigation and reloads within the existing server session.
// Production replaces this map/clock with durable jobs and a document conversion worker.
export function createPrintQueue(now = () => Date.now(), random = Math.random) {
  const jobs = new Map<string, StoredTask>()
  function update(entry: StoredTask): PrintTask {
    const elapsed = now() - entry.task.createdAt, wait = entry.scenario === 'slow' ? 45000 : 5000
    const status = elapsed < wait ? 'queued' : elapsed < wait + 5000 ? 'running' : entry.scenario === 'failure' ? 'failed' : 'ready'
    return { ...entry.task, status, stage: status === 'running' ? '正在转换为 PDF' : undefined, error: status === 'failed' ? '模拟文档转换失败，请重新生成。' : undefined }
  }
  function entry(id: string, source: PrintSource) {
    const result = jobs.get(id)
    if (!result || (result.task.kind !== source.kind || result.task.sourceId !== source.id)) throw new AppError('NOT_FOUND', '生成记录不存在。')
    return result
  }
  return {
    submit(source: PrintSource, data: Record<string, unknown>) {
      const documentType = source.kind === 'samples' ? 'sample' : 'commission'
      if (data.documentType !== documentType || data.documentCode !== source.code) throw new AppError('VALIDATION', '打印对象类型或单号不匹配。')
      if (!source.canPrint) throw new AppError('BUSINESS_RULE', '该委托下暂无样品，无法打印。')
      if (!['product', 'engineering'].includes(String(data.type)) || !['normal', 'extended'].includes(String(data.layout)) || !Array.isArray(data.copies) || !data.copies.length || data.copies.length > 4 || data.copies.some(n => !Number.isInteger(n) || n < 1 || n > (data.type === 'product' ? 4 : 3))) throw new AppError('VALIDATION', '请选择有效的委托单类型、版式和联次。')
      // Explicit scenarios are only used by automated HTTP tests; the page submits business options.
      if (data.scenario !== undefined && !['normal', 'slow', 'failure', 'expired'].includes(String(data.scenario))) throw new AppError('VALIDATION', '无效的模拟场景。')
      const copies = [...new Set(data.copies as number[])].sort()
      for (const stored of jobs.values()) {
        const task = update(stored)
        if (task.kind === source.kind && task.sourceId === source.id && task.type === data.type && task.layout === data.layout && task.copies.join() === copies.join() && (task.status === 'queued' || task.status === 'running')) return task
      }
      // Draw once per new job. Polling and reopening must never change its outcome.
      const draw = data.scenario === undefined ? random() : 0
      const scenario = (data.scenario ?? (draw < 0.7 ? 'normal' : draw < 0.85 ? 'slow' : draw < 0.95 ? 'failure' : 'expired')) as PrintScenario
      const createdAt = now()
      const task: PrintTask = { id: randomUUID(), documentType, documentCode: source.code, kind: source.kind, sourceId: source.id, type: data.type as PrintTask['type'], layout: data.layout as PrintTask['layout'], copies, createdAt, expiresAt: createdAt + (scenario === 'expired' ? 9000 : 86400000), status: 'queued' }
      jobs.set(task.id, { task, snapshot: structuredClone(source), scenario })
      return task
    },
    get(id: string, source: PrintSource) { return update(entry(id, source)) },
    list(source: PrintSource, page: number, pageSize: number) {
      const records = [...jobs.values()].filter(j => j.task.kind === source.kind && j.task.sourceId === source.id).sort((a, b) => b.task.createdAt - a.task.createdAt)
      return { items: records.slice((page - 1) * pageSize, page * pageSize).map(update), total: records.length, page, pageSize }
    },
    async pdf(id: string, source: PrintSource) {
      const stored = entry(id, source), task = update(stored)
      if (task.status !== 'ready') throw new AppError('BUSINESS_RULE', '文件尚未生成。')
      if (task.expiresAt <= now()) throw new AppError('BUSINESS_RULE', '文件已过期，请重新生成。')
      const font = resolve('public/fonts/poppins-0.ttf')
      const printer = new PdfPrinter({ Demo: { normal: font, bold: font, italics: font, bolditalics: font } })
      // Preview fixture only. Production decides document contents from the request's type and code.
      const r = stored.snapshot
      const content: Content[] = task.copies.flatMap((copy, index): Content[] => [
        { text: '委托单', fontSize: 22, alignment: 'center', ...(index ? { pageBreak: 'before' as const } : {}) },
        { text: `${printDescription({ ...task, copies: [copy] })}（${copyNames[copy - 1]}）`, margin: [0, 16, 0, 16] },
        { table: { widths: [100, '*'], body: [[task.documentType === 'sample' ? '样品编号' : '委托编号', r.code], ['名称', r.name || '—'], ['委托单位', r.preview.customer || '—'], ['委托人', r.preview.contact || '—'], ['联系电话', r.preview.phone || '—'], ['检测项目', r.preview.projects.join('；') || '—']] } },
      ])
      const doc = printer.createPdfKitDocument({ defaultStyle: { font: 'Demo', fontSize: 11 }, pageSize: task.layout === 'extended' ? { width: 595.28, height: 1000 } : 'A4', content })
      return new Promise<Buffer>((resolve, reject) => { const chunks: Buffer[] = []; doc.on('data', chunk => chunks.push(chunk)); doc.on('end', () => resolve(Buffer.concat(chunks))); doc.on('error', reject); doc.end() })
    },
  }
}
