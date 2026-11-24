import { authedFetch } from './http'

export interface XlsxColumn {
  label: string
  key: string
  width?: number
}

export async function exportRowsXlsx(filename: string, columns: XlsxColumn[], rows: Record<string, unknown>[]) {
  const response = await authedFetch('/api/exports/xlsx', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, columns, rows }),
  })
  if (!response.ok) throw new Error(`导出失败（${response.status}）`)
  const type = response.headers.get('content-type') || ''
  if (type.includes('json')) {
    const body = await response.json()
    throw new Error(body.message || '导出失败')
  }
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = `${filename}.xlsx`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
