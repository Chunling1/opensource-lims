import { createRequire } from 'node:module'
import { AppError } from '../src/services/common/errors'
import type { OriginalRecord } from '../src/types/testing/originalRecords'
// Keep the CommonJS PDF engine on Node's loader, including under Vite/Playwright.
const { PDFDocument } = createRequire(import.meta.url)('pdf-lib') as typeof import('pdf-lib')

export async function mergeOriginalPdf(records: OriginalRecord[]) {
  const output = await PDFDocument.create()
  const files = records.flatMap(record => {
    if (!record.files?.length) throw new AppError('BUSINESS_RULE', `“${record.name}”尚未导入 PDF，请在文件列表中更新 ELN 记录。`)
    return record.files
  })
  for (const file of files) {
    try {
      const bytes = Buffer.from(file.dataUrl.split(',')[1] || '', 'base64')
      if (file.type === 'application/pdf') {
        const source = await PDFDocument.load(bytes, { updateMetadata: false })
        if (!source.getPageCount()) throw new Error('empty PDF')
        // A single PDF retains its original bytes, including annotations and signatures.
        if (files.length === 1) return { bytes, pageCount: source.getPageCount() }
        if (source.getForm().getFields().length) source.getForm().flatten()
        for (const page of await output.copyPages(source, source.getPageIndices())) output.addPage(page)
      } else if (['image/png', 'image/jpeg'].includes(file.type)) {
        // Historical image originals remain visible in the combined preview.
        const image = file.type === 'image/png' ? await output.embedPng(bytes) : await output.embedJpg(bytes)
        const page = output.addPage([595.28, 841.89]), size = image.scaleToFit(555.28, 801.89)
        page.drawImage(image, { x: (page.getWidth() - size.width) / 2, y: (page.getHeight() - size.height) / 2, ...size })
      } else throw new Error('unsupported file')
    } catch (cause) { throw new AppError('BUSINESS_RULE', `无法合并“${file.name}”：文件可能损坏、加密或格式不支持。请检查或重新上传；原文件已保留。`, { cause }) }
  }
  if (!output.getPageCount()) throw new AppError('BUSINESS_RULE', '暂无原始记录，请先导入文件。')
  return { bytes: Buffer.from(await output.save()), pageCount: output.getPageCount() }
}
