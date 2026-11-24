import { describe, expect, it } from 'vitest'
import { parseTableColumns, tableCellText, tableCellPreview, tableSelectionState } from '../../src/services/common/table'
import type { TableColumn } from '../../src/types/common/table'

describe('shared table configuration', () => {
  const columns = [
    { key: 'name', label: '名称', required: true },
    { key: 'amount', label: '金额', default: true, money: true },
    { key: 'description', label: '描述', truncate: 2, fullTitle: true },
  ] as const satisfies readonly TableColumn[]

  it('uses metadata for fixed columns and canonical order without a code field', () => {
    expect(parseTableColumns(columns, undefined)).toEqual(['name', 'amount'])
    expect(parseTableColumns(columns, '')).toEqual(['name'])
    expect(parseTableColumns(columns, 'description,description,unknown')).toEqual(['name', 'description'])
    expect(parseTableColumns(columns, 'unknown')).toEqual(['name', 'amount'])
    expect(parseTableColumns(columns, ['description'])).toEqual(['name', 'amount'])
  })

  it('keeps full text and Unicode intact while truncating the display only', () => {
    const full = '中😀文\n长名称'
    expect(tableCellText(full, {})).toBe(full)
    expect(tableCellPreview(full, 2)).toBe('中😀…')
    expect(tableCellPreview('中😀', 2)).toBe('中😀')
    expect(tableCellPreview(full)).toBe(full)
  })

  it('distinguishes missing amounts from zero without rounding the underlying data', () => {
    expect(tableCellText(0, { money: true })).toBe('0.00')
    expect(tableCellText(12.345, { money: true })).toBe('12.35')
    for (const value of [undefined, null, NaN, Infinity, '12.00']) expect(tableCellText(value, { money: true })).toBe('—')
    expect(tableCellText('  ', {})).toBe('—')
    expect(tableCellText(0, {})).toBe('0')
  })

  it('computes header selection only from eligible rows on the current page', () => {
    expect(tableSelectionState(['a', 'b'], ['a', 'disabled', 'other-page'])).toEqual({ all: false, partial: true })
    expect(tableSelectionState(['a', 'b'], ['a', 'b', 'other-page'])).toEqual({ all: true, partial: false })
    expect(tableSelectionState(['a', 'b'], ['disabled', 'other-page'])).toEqual({ all: false, partial: false })
    expect(tableSelectionState([], ['other-page'])).toEqual({ all: false, partial: false })
  })
})
