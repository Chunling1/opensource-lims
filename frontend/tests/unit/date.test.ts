import { expect, it } from 'vitest'
import { clientYearRange, clientMonthRange } from '../../src/services/common/date'

it('defaults to the previous calendar month and clamps month ends across years', () => {
  expect(clientMonthRange(new Date(2026, 8, 26))).toEqual({ from: '2026-08-26', to: '2026-09-26' })
  const date = new Date(2026, 2, 31)
  expect(clientMonthRange(date)).toEqual({ from: '2026-02-28', to: '2026-03-31' })
  expect(date.getDate()).toBe(31)
  expect(clientMonthRange(new Date(2024, 2, 31))).toEqual({ from: '2024-02-29', to: '2024-03-31' })
  expect(clientMonthRange(new Date(2026, 0, 31))).toEqual({ from: '2025-12-31', to: '2026-01-31' })
})

it('uses a local calendar year and clamps leap days without changing the supplied date', () => {
  expect(clientYearRange(new Date(2026, 8, 22, 0, 1))).toEqual({ from: '2025-09-22', to: '2026-09-22' })
  const leap = new Date(2024, 1, 29, 23, 59)
  expect(clientYearRange(leap)).toEqual({ from: '2023-02-28', to: '2024-02-29' })
  expect(leap.getDate()).toBe(29)
  expect(clientYearRange(new Date(2026, 0, 1))).toEqual({ from: '2025-01-01', to: '2026-01-01' })
})
