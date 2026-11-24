import {describe,it,expect} from 'vitest'
import {formatTrialEnvironment,parseTrialEnvironment} from './trialEnvironment'

describe('template environment input / four platform fields',()=>{
 it('round-trips separate values without adding units or dropping precision',()=>{
  const values={calibrationPlace:'上海实验室',temperature:'23.00',humidity:'50',pressure:'1013.25'}
  expect(formatTrialEnvironment(values)).toBe('地点：上海实验室；温度：23.00；湿度：50；压力：1013.25')
  expect(parseTrialEnvironment(formatTrialEnvironment(values))).toEqual(values)
 })
 it('keeps empty values, zero, punctuation and significant whitespace',()=>{
  const values={calibrationPlace:' A；B; "C"\nD\\E ',temperature:'0',humidity:'',pressure:' 1013 '}
  expect(parseTrialEnvironment(formatTrialEnvironment(values))).toEqual(values)
 })
 it('accepts reordered labels and ASCII separators',()=>{
  expect(parseTrialEnvironment('压力:1000;地点:一号室;湿度:50;温度:22')).toEqual({calibrationPlace:'一号室',temperature:'22',humidity:'50',pressure:'1000'})
 })
 it.each(['地点：A；温度：23','地点：A；温度：23；湿度：50；湿度：60','地点：A；温度：23；湿度：50；压力："broken','地点：A；温度：23；湿度：50；压力：1000；噪声：1'])('rejects incomplete or ambiguous input: %s',input=>expect(()=>parseTrialEnvironment(input)).toThrow('未被覆盖'))
 it('allows an explicit empty input to clear all four fields together',()=>{
  expect(parseTrialEnvironment('')).toEqual({calibrationPlace:'',temperature:'',humidity:'',pressure:''})
 })
})
