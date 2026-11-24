import { randomUUID } from 'node:crypto'
import { resolve } from 'node:path'
import PdfPrinter from 'pdfmake'
import type { TDocumentDefinitions } from 'pdfmake/interfaces'
import { AppError } from '../src/services/common/errors'
import type { TaskPrintContext, TaskPrintJob } from '../src/types/testing/taskPrint'
import type { PrintScenario } from '../src/types/commissions/commissionPrint'

export interface TaskPrintSource extends TaskPrintContext {
  submittedBy: { id: string; name: string }
  snapshot: { commissionCode: string; parameters: string[]; customer: string; commissionDate: string; projectAddress: string
    assignedById: string; assignedBy: string; dataEntryPerson: string; tester1: string; tester2: string; assignedDate: string }
}
export function taskPrintDocument(source: TaskPrintSource): TDocumentDefinitions {
  const info = source.snapshot
  return {
    pageSize: 'A4', pageMargins: [40, 40, 40, 40], defaultStyle: { font: 'Demo', fontSize: 11 },
    content: [
      { text: '检测任务单（演示）', alignment: 'center', fontSize: 22, margin: [0, 0, 0, 20] },
      { table: { widths: [110, '*'], body: [
        ['样品编号', source.code], ['委托编号', info.commissionCode], ['检测方案', source.testPlan], ['样品/工程名称', source.name],
        ['检测参数', info.parameters.join('；')], ['委托单位', info.customer], ['委托日期', info.commissionDate], ['工程地址', info.projectAddress],
        ['分配人工号', info.assignedById], ['分配人姓名', info.assignedBy], ['数据录入人', info.dataEntryPerson],
        ['检测人1', info.tester1], ['检测人2', info.tester2], ['分配日期', info.assignedDate],
      ] }, layout: { paddingTop: () => 7, paddingBottom: () => 7 } },
    ],
    footer: (page, pages) => ({ stack: [{ text: '演示模板，任用于验证任务单打印流程。', color: '#666666' }, { text: `${page} / ${pages}`, margin: [0, 4, 0, 0] }], alignment: 'center', fontSize: 9 }),
  }
}
// Mock queue is isolated from commission prints and survives navigation within a server session.
export function createTaskPrintQueue(now = () => Date.now(), random = Math.random) {
  const jobs = new Map<string, { task: TaskPrintJob; snapshot: TaskPrintSource; scenario: PrintScenario; pdf?: Promise<Buffer> }>()
  function update(stored: { task: TaskPrintJob; scenario: PrintScenario }, source: TaskPrintSource): TaskPrintJob {
    const elapsed = now() - stored.task.createdAt, wait = stored.scenario === 'slow' ? 45000 : 5000
    const status = elapsed < wait ? 'queued' : elapsed < wait + 5000 ? 'running' : stored.scenario === 'failure' ? 'failed' : 'ready'
    return { ...stored.task, historical: stored.task.sourceVersion !== source.version, status, stage: status === 'running' ? '正在转换为 PDF' : undefined, error: status === 'failed' ? '模拟文档转换失败，请重新生成。' : undefined }
  }
  function entry(id: string, source: TaskPrintSource) {
    const stored = jobs.get(id)
    if (!stored || stored.task.sourceId !== source.id) throw new AppError('NOT_FOUND', '生成记录不存在。')
    return stored
  }
  return {
    submit(source: TaskPrintSource, data: Record<string, unknown>) {
      if (!Number.isSafeInteger(data.version) || Number(data.version) < 1) throw new AppError('BAD_REQUEST', '记录版本有误。')
      
      if (!source.canPrint) throw new AppError('BUSINESS_RULE', '仅任务分配中及后续阶段的样品可以生成任务单。')
      if (Object.keys(data).some(key => !['version', 'scenario'].includes(key))) throw new AppError('BAD_REQUEST', '任务单打印参数有误。')
      if (data.scenario !== undefined && !['normal', 'slow', 'failure', 'expired'].includes(String(data.scenario))) throw new AppError('BAD_REQUEST', '无效的模拟场景。')
      for (const stored of jobs.values()) {
        const task = update(stored, source)
        if (task.sourceId === source.id && !task.historical && ['queued', 'running'].includes(task.status)) return task
      }
      const draw = data.scenario === undefined ? random() : 0
      const scenario = (data.scenario ?? (draw < 0.7 ? 'normal' : draw < 0.85 ? 'slow' : draw < 0.95 ? 'failure' : 'expired')) as PrintScenario
      const createdAt = now()
      const task: TaskPrintJob = { id: randomUUID(), sourceId: source.id, sourceVersion: source.version, code: source.code, submittedBy: { ...source.submittedBy }, createdAt, expiresAt: createdAt + (scenario === 'expired' ? 9000 : 86400000), status: 'queued', historical: false }
      jobs.set(task.id, { task, snapshot: structuredClone(source), scenario })
      return structuredClone(task)
    },
    get(id: string, source: TaskPrintSource) { return update(entry(id, source), source) },
    list(source: TaskPrintSource, page: number, pageSize: number) {
      const records = [...jobs.values()].filter(job => job.task.sourceId === source.id).reverse().sort((a, b) => b.task.createdAt - a.task.createdAt)
      return { items: records.slice((page - 1) * pageSize, page * pageSize).map(stored => update(stored, source)), total: records.length, page, pageSize }
    },
    async pdf(id: string, source: TaskPrintSource) {
      const stored = entry(id, source), task = update(stored, source)
      if (task.status !== 'ready') throw new AppError('BUSINESS_RULE', '文件尚未生成。')
      if (task.expiresAt <= now()) throw new AppError('BUSINESS_RULE', '文件已过期，请重新生成。')
      if (stored.pdf) return stored.pdf
      const font = resolve('public/fonts/poppins-0.ttf')
      const printer = new PdfPrinter({ Demo: { normal: font, bold: font, italics: font, bolditalics: font } })
      const doc = printer.createPdfKitDocument(taskPrintDocument(stored.snapshot))
      stored.pdf = new Promise<Buffer>((resolve, reject) => { const chunks: Buffer[] = []; doc.on('data', chunk => chunks.push(chunk)); doc.on('end', () => resolve(Buffer.concat(chunks))); doc.on('error', reject); doc.end() }).catch(error => { stored.pdf = undefined; throw error })
      return stored.pdf
    },
  }
}
