import PdfPrinter from 'pdfmake'
import { resolve } from 'node:path'
import type { Content } from 'pdfmake/interfaces'
import { trialDatesText, trialEquipmentText, type EntryDetail } from '../src/types/testing/dataEntryDetail'

// Minimal, uncompressed OPC package for the mock Word download; not a production renderer.
function zip(files: Record<string, string>) {
  const chunks: Buffer[] = [], directory: Buffer[] = []; let offset = 0
  for (const [path, text] of Object.entries(files)) {
    const name = Buffer.from(path), data = Buffer.from(text); let crc = 0xffffffff
    for (const byte of data) { crc ^= byte; for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0) }
    crc = (crc ^ 0xffffffff) >>> 0
    const local = Buffer.alloc(30); local.writeUInt32LE(0x04034b50); local.writeUInt16LE(20, 4); local.writeUInt32LE(crc, 14); local.writeUInt32LE(data.length, 18); local.writeUInt32LE(data.length, 22); local.writeUInt16LE(name.length, 26)
    const central = Buffer.alloc(46); central.writeUInt32LE(0x02014b50); central.writeUInt16LE(20, 4); central.writeUInt16LE(20, 6); central.writeUInt32LE(crc, 16); central.writeUInt32LE(data.length, 20); central.writeUInt32LE(data.length, 24); central.writeUInt16LE(name.length, 28); central.writeUInt32LE(offset, 42)
    chunks.push(local, name, data); directory.push(central, name); offset += local.length + name.length + data.length
  }
  const table = Buffer.concat(directory), end = Buffer.alloc(22); end.writeUInt32LE(0x06054b50); end.writeUInt16LE(Object.keys(files).length, 8); end.writeUInt16LE(Object.keys(files).length, 10); end.writeUInt32LE(table.length, 12); end.writeUInt32LE(offset, 16)
  return Buffer.concat([...chunks, table, end])
}
const xml = (value: string) => value.replace(/[<>&"']/g, char => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' })[char]!).replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, '')
function fields(detail: EntryDetail) {
  const { sample, form, options } = detail
  const person = (id: string) => [...options.people, ...options.reviewers, ...options.approvers].find(row => row.id === id)?.name || ''
  return [`样品编号：${sample.code}`, `样品/工程名称：${sample.name}`, `委托单位：${sample.customer}`, `检测方案：${sample.details?.testPlan || ''}`, ...(form.showStandard ? [`检测依据：${sample.details?.testBasis || ''}`] : []), `结论：${form.conclusion}`, `结论状态：${form.conclusionStatus}`, `不合格参数：${form.failedParameters}`, `备注：${form.notes}`, `试验人：${person(form.tester1Id)} ${person(form.tester2Id)}`, `试验日期：${trialDatesText(form.testDates)}`, `审核人：${person(form.reviewerId)} 批准人：${person(form.approverId)}`, `试验环境：${form.environment}`, `试验设备：${trialEquipmentText(form, options.equipment)}`, ...(form.calibrationEnabled ? [`校准日期：${form.calibrationDate}`] : []), ...(form.reportDateEnabled ? [`报告日期：${form.reportDate}`] : [])]
}
export function entryWord(detail: EntryDetail, complete = false) {
  const p = (text: string) => `<w:p><w:r><w:t xml:space="preserve">${xml(text)}</w:t></w:r></w:p>`
  const page = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
  const body = [p(complete ? '检测报告（自动生成完整报告 · 演示）' : '检测报告（演示模板）'), p(detail.sample.reportCode), ...detail.template.labels.map(p), p(`模板版本：${detail.template.version}`), p('仅用于模拟联调；正式模板和实际文档转换由后台接入。'), page, ...(complete ? [p('检测信息'), p(`检测参数：${detail.sample.projects.join('、')}`)] : []), ...fields(detail).map(p), ...(detail.layoutId === 'extended' ? [page, p('扩展首页（演示）')] : []), ...(complete ? [] : [page, p('可补充报告内容后，将完整 DOCX 上传至“补充完整报告”。')])].join('')
  return zip({ '[Content_Types].xml': '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>', '_rels/.rels': '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>', 'word/document.xml': `<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>${body}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr></w:body></w:document>` })
}
export async function entryPdf(detail: EntryDetail, template = false) {
  const font = resolve('public/fonts/poppins-0.ttf'), printer = new PdfPrinter({ Demo: { normal: font, bold: font, italics: font, bolditalics: font } })
  const content: Content[] = [{ text: template ? '报告模板预览（模拟结果）' : '最终报告预览（模拟结果）', fontSize: 20 }, { text: '此文件用于验证流程，未实际转换上传文档或保留 Conclusion.docx 的结论格式。', margin: [0, 12, 0, 12] }, { text: `${detail.template.labels.join(' · ')} · 模板版本 ${detail.template.version}`, margin: [0, 0, 0, 12] }, ...fields(detail).map(text => ({ text, margin: [0, 0, 0, 8] } as Content))]
  if (detail.layoutId === 'extended') content.push({ text: '扩展首页（演示）', pageBreak: 'before', fontSize: 18 })
  if (!template) content.push({ text: '后台报告处理清单（模拟）', pageBreak: 'before', fontSize: 18 }, { text: detail.files.some(file => file.kind === 'report') ? '已提供补充完整报告，报告来源与编排由后台决定。' : '根据已保存的表单生成系统报告。' }, ...detail.files.filter(file => file.kind !== 'original').map(file => ({ text: `${file.kind === 'report' ? '补充完整报告' : file.name.toLowerCase() === 'conclusion.docx' ? '额外文件 · 结论内容文件' : '额外文件'}：${file.name}`, margin: [0, 10, 0, 0] } as Content)))
  const doc = printer.createPdfKitDocument({ content, defaultStyle: { font: 'Demo', fontSize: 11 }, pageMargins: [40, 40, 40, 40], footer: (page, total) => ({ text: `模拟结果 · ${page}/${total}`, alignment: 'center' }) })
  return new Promise<Buffer>((resolve, reject) => { const chunks: Buffer[] = []; doc.on('data', chunk => chunks.push(chunk)); doc.on('error', reject); doc.on('end', () => resolve(Buffer.concat(chunks))); doc.end() })
}
