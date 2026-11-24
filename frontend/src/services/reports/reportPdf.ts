import { AppError } from '../common/errors'
import type { Content, TDocumentDefinitions } from 'pdfmake/interfaces'
import { limsService } from '../business/limsService'
let fontReady: Promise<void> | undefined
let pdfMake: typeof import('pdfmake/build/pdfmake')
async function ensureFont() {
  if (!fontReady) fontReady = (async () => {
    pdfMake = (await import('pdfmake/build/pdfmake')).default
    const response = await fetch(`${import.meta.env.BASE_URL}fonts/poppins-0.ttf`)
    if (!response.ok) throw new AppError('RESOURCE_LOAD', '本地中文字体加载失败。')
    const bytes = new Uint8Array(await response.arrayBuffer()); let binary = ''
    for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192))
    pdfMake.vfs = { 'NotoSans.otf': btoa(binary) }
    pdfMake.fonts = { NotoSans: { normal: 'NotoSans.otf', bold: 'NotoSans.otf', italics: 'NotoSans.otf', bolditalics: 'NotoSans.otf' } }
  })().catch(e => { fontReady = undefined; throw e instanceof AppError ? e : new AppError('RESOURCE_LOAD', '报告生成组件或本地中文字体加载失败，请重试。', { cause: e }) })
  return fontReady
}
export interface ReportSnapshot { code: string; name: string; conclusion: string; customer: string; orderCode: string; template: Record<string, string | string[]>; results: { sample: string; sampleCode: string; project: string; method: string; result: string; unit: string; judgment: string; source: string }[]; reviewer: string; approver: string; signedAt: string }
export function reportDocument(snapshot: ReportSnapshot): TDocumentDefinitions {
  const basics = Array.isArray(snapshot.template.basicFields) ? snapshot.template.basicFields : ['客户', '委托编号']
  const columns = String(snapshot.template.resultColumns || '样品,项目,方法,结果,单位,判定').split(/[,，]/).map(s => s.trim())
  const resultCell = (r: ReportSnapshot['results'][number], label: string) => ({ '样品': `${r.sample}\n${r.sampleCode}`, '项目': r.project, '方法': r.method, '结果': String(r.result), '单位': r.unit, '判定': r.judgment, '来源': r.source }[label] || '')
  const content: Content[] = [
    { text: String(snapshot.template.header), alignment: 'center', fontSize: 16, margin: [0, 0, 0, 10] },
    { text: String(snapshot.template.title), alignment: 'center', fontSize: 22, margin: [0, 0, 0, 20] },
    { text: `报告编号：${snapshot.code}`, margin: [0, 0, 0, 8] },
    { text: [basics.includes('委托编号') ? `委托编号：${snapshot.orderCode}` : '', basics.includes('客户') ? `委托单位：${snapshot.customer}` : '', basics.includes('样品') ? `样品：${[...new Set(snapshot.results.map(r => r.sampleCode))].join('、')}` : '', basics.includes('方法') ? `检测依据：${[...new Set(snapshot.results.map(r => r.method))].join('、')}` : ''].filter(Boolean).join('\n'), margin: [0, 0, 0, 14] },
    { table: { headerRows: 1, widths: columns.map(() => '*'), body: [ columns, ...snapshot.results.map(r => columns.map(c => resultCell(r, c))) ] }, layout: 'lightHorizontalLines' },
    { text: `结论：${snapshot.conclusion}`, margin: [0, 18, 0, 14] },
    { text: `${snapshot.template.signatureLabel}\n审核：${snapshot.reviewer}    批准：${snapshot.approver}\n签发日期：${new Date(snapshot.signedAt).toLocaleDateString('zh-CN')}`, margin: [0, 10, 0, 10] },
  ]
  if (snapshot.template.appendix) content.push({ text: String(snapshot.template.appendix), margin: [0, 15, 0, 0] })
  return { info: { title: `${snapshot.code} 检测报告`, author: String(snapshot.template.header), creationDate: new Date(snapshot.signedAt) }, pageSize: 'A4', pageMargins: [40, 40, 40, 60], defaultStyle: { font: 'NotoSans', fontSize: 10 }, content, footer: (page, count) => ({ text: `${snapshot.template.footer}    第 ${page} / ${count} 页`, alignment: 'center', fontSize: 8, margin: [35, 15, 35, 0] }) }
}
export async function generateReportPdf(id: string) {
  const { record, attachments } = await limsService.detail('reports', id)
  if (!record.data.signedSnapshot) throw new AppError('BUSINESS_RULE', '报告尚未签发。')
  if (['已替代', '已作废'].includes(record.status)) throw new AppError('BUSINESS_RULE', '此报告已失效，不能下载。')
  const archived = attachments.find(a => a.id === `signed-pdf-${id}`)
  if (archived) return (await limsService.attachment(archived.id)).blob
  const snapshot = JSON.parse(String(record.data.signedSnapshot)) as ReportSnapshot
  return renderSnapshotPdf(snapshot)
}
export async function renderSnapshotPdf(snapshot: ReportSnapshot) {
  await ensureFont()
  return new Promise<Blob>((resolve, reject) => { try { pdfMake.createPdf(reportDocument(snapshot)).getBlob(blob => resolve(blob)) } catch (e) { reject(e) } })
}
export function downloadBlob(blob: Blob, name: string) { const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000) }

export async function printTablePdf(title: string, headers: string[], rows: string[][]) {
  const target = window.open('', '_blank')
  if (!target) throw new AppError('BUSINESS_RULE', '请允许打开打印窗口后重试。')
  try {
    await ensureFont()
    pdfMake.createPdf({ pageSize: 'A4', pageOrientation: 'landscape', defaultStyle: { font: 'NotoSans', fontSize: 9 }, content: [{ text: title, fontSize: 16, margin: [0, 0, 0, 16] }, { table: { headerRows: 1, widths: headers.map(() => '*'), body: [headers, ...rows] }, layout: 'lightHorizontalLines' }] }).print({}, target)
  } catch (issue) { target.close(); throw issue }
}
