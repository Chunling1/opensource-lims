import { describe, expect, it } from 'vitest'
import { joinBasisText, readBasisSeparators, retainBasisSeparators, validBasisSeparator } from '../../src/services/commissions/testBasisText'

describe('protected standard text', () => {
  const labels = ['A《标准；甲》', 'B《标准乙》', 'C《标准丙》']
  it('matches whole known labels and only extracts separators', () => {
    expect(readBasisSeparators(joinBasisText(labels, ['；', '\n']), labels)).toEqual(['；', '\n'])
    expect(readBasisSeparators(joinBasisText(labels, ['', '、 ']), labels)).toEqual(['', '、 '])
    for (const text of [joinBasisText(labels, ['新标准', '\n']), joinBasisText(labels, ['；', '\n']) + '追加', joinBasisText(labels, ['；', '\n']).replace('甲', '假'), labels.slice(1).join('；'), [...labels].reverse().join('；')]) expect(readBasisSeparators(text, labels)).toBeNull()
    expect(validBasisSeparator('')).toBe(false)
    expect(validBasisSeparator('；\n')).toBe(true)
    expect(validBasisSeparator('---')).toBe(false)
    expect(validBasisSeparator('\t')).toBe(false)
  })
  it('retains only unchanged neighboring pairs after list edits', () => {
    expect(retainBasisSeparators(['a', 'b', 'c', 'd'], ['\n', '/', '、'], ['a', 'c', 'd', 'e'])).toEqual(['；', '、', '；'])
  })
})
