import { expect, it, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import ProductionDatePicker from '@/components/ProductionDatePicker.vue'
import { productionDateBoundary, sampleDateOrderErrors, savedSampleDates, isProductionDateValid } from '@/composables/sampleDateRules'
vi.mock('@/stores/session', () => ({useSessionStore: () => ({canOverrideWorkflowDate: false})}))

it('keeps month precision and requires explicit day when changing precision', async () => {
  const w = shallowMount(ProductionDatePicker, {props: {modelValue: '2026-10', nextDate: '2026-10-22'}})
  expect((w.get('input[type="month"]').element as HTMLInputElement).value).toBe('2026-10')
  expect(w.get('input[type="month"]').attributes('max')).toBe('2026-10')
  await w.get('select').setValue('day')
  expect(w.emitted('update:modelValue')?.at(-1)).toEqual([''])
  await w.setProps({modelValue: '2026-10-22'})
  await w.get('select').setValue('month')
  expect(w.emitted('update:modelValue')?.at(-1)).toEqual(['2026-10'])
  w.unmount()
})
it('compares month boundaries without relaxing other date order', () => {
  expect(productionDateBoundary('2026-13')).toBe('')
  expect(sampleDateOrderErrors({produceDate:'2026-10',sendDate:'2026-10-01'})).toEqual([])
  expect(sampleDateOrderErrors({produceDate:'2026-11',sendDate:'2026-10-22'})).toContain('送样日期不得早于生产日期')
  expect(sampleDateOrderErrors({produceDate:'2026-10-22',sendDate:'2026-10-21'})).toContain('送样日期不得早于生产日期')
})

it.each(['/', '—', 'N/A', '未提供'])('round-trips custom production text %s and switches back without inventing a date', async marker => {
  const w = shallowMount(ProductionDatePicker, {props: {modelValue: '2026-10-24'}})
  await w.get('select').setValue('custom')
  expect(w.emitted('update:modelValue')?.at(-1)).toEqual([''])
  await w.setProps({modelValue: ''})
  await w.get('input[type="text"]').setValue(marker)
  expect(w.emitted('update:modelValue')?.at(-1)).toEqual([marker])
  await w.setProps({modelValue: marker})
  expect(w.get('select').element.value).toBe('custom')
  await w.setProps({disabled: true})
  expect(w.get('input[type="text"]').attributes()).toHaveProperty('disabled')
  w.unmount()
  const reopened = shallowMount(ProductionDatePicker, {props: {modelValue: marker}})
  expect((reopened.get('input[type="text"]').element as HTMLInputElement).value).toBe(marker)
  await reopened.get('select').setValue('month')
  expect(reopened.emitted('update:modelValue')?.at(-1)).toEqual([''])
  reopened.unmount()
  expect(savedSampleDates({rawSample: {produceDate: marker}}).produceDate).toBe(marker)
  expect(isProductionDateValid(marker)).toBe(true)
  expect(productionDateBoundary(marker)).toBe('')
  expect(sampleDateOrderErrors({produceDate: marker, sampleTime: '2026-10-24', sendDate: '2026-10-23'}))
    .toEqual(['送样日期不得早于抽样日期'])
})

it.each(['2026-13', '2026-02-29', '2026-2'])('does not reinterpret invalid date %s as a marker', value => {
  expect(isProductionDateValid(value)).toBe(false)
})
