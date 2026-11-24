import type { RegistrationSample } from '../src/types/commissions/registration'
import type { Actor } from '../src/types/lims'
import type { ElnRecord } from '../src/types/testing/originalRecords'
import PdfPrinter from 'pdfmake'
import { resolve } from 'node:path'
export interface OriginalAdapters { eln: (sample: RegistrationSample, actor: Actor) => ElnRecord[]; pdf: (sample: RegistrationSample, actor: Actor, record: ElnRecord) => Promise<Uint8Array> }
export const originalAdapters: OriginalAdapters = {
  eln: sample => Array.from({ length: 3 }, (_, index) => ({ systemId: 'demo-eln', id: `${sample.id}-eln-${index + 1}`, sampleCode: sample.code, name: `${sample.name} · ELN 原始记录 ${index + 1}`, status: index === 0 ? '已审核' : '已填写', version: '1', updatedAt: '2026-09-28T08:00:00Z', fields: [{ label: '样品编号', value: sample.code }, { label: '检测项目', value: sample.name }, { label: '记录内容', value: 'ELN 实时查看演示；尚未连接外部 ELN。' }], simulated: true })),
  async pdf(_sample, _actor, record) {
    const font = resolve('public/fonts/poppins-0.ttf')
    const printer = new PdfPrinter({ Demo: { normal: font, bold: font, italics: font, bolditalics: font } })
    const doc = printer.createPdfKitDocument({ defaultStyle: { font: 'Demo', fontSize: 11 }, content: [
      { text: 'ELN 原始记录（模拟导出）', fontSize: 20 }, { text: record.name, margin: [0, 12, 0, 12] },
      `来源：${record.systemId} / ${record.id}`, `版本：${record.version}　更新时间：${record.updatedAt}`,
      ...record.fields.map(field => ({ text: `${field.label}：${field.value}`, margin: [0, 8, 0, 0] as [number, number, number, number] })),
      { text: '此 PDF 为模拟 ELN 导出文件，真实外部系统尚未接入。', margin: [0, 20, 0, 0] },
    ] })
    return new Promise<Buffer>((resolve, reject) => { const chunks: Buffer[] = []; doc.on('data', chunk => chunks.push(chunk)); doc.on('error', reject); doc.on('end', () => resolve(Buffer.concat(chunks))); doc.end() })
  },
}

