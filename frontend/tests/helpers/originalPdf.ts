import { createRequire } from 'node:module'
export const { PDFDocument } = createRequire(import.meta.url)('pdf-lib') as typeof import('pdf-lib')
export async function originalPdf(widths = [595], label = 'Original record') {
  const doc = await PDFDocument.create()
  for (const width of widths) doc.addPage([width, 842]).drawText(label, { x: 40, y: 780, size: 18 })
  return Buffer.from(await doc.save())
}
