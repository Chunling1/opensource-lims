import { AppError } from './errors'
// Small arithmetic grammar: numeric literals, x, parentheses and + - * /.
export function calculateFormula(formula: string, x: number): number {
  if (formula.length > 200 || !Number.isFinite(x)) throw new AppError('BUSINESS_RULE', '公式或原始值无效。')
  const tokens = formula.match(/(?:\d+(?:\.\d*)?|\.\d+)|x|[()+*/-]/g) ?? []
  if (tokens.join('') !== formula.replace(/\s/g, '')) throw new AppError('BUSINESS_RULE', '公式仅支持 x、数字、括号及加减乘除。')
  let index = 0, depth = 0
  const atom = (): number => {
    if (++depth > 40) throw new AppError('BUSINESS_RULE', '公式嵌套过深。')
    const t = tokens[index++]; let value: number
    if (t === '+') value = atom()
    else if (t === '-') value = -atom()
    else if (t === '(') { value = expression(); if (tokens[index++] !== ')') throw new AppError('BUSINESS_RULE', '公式括号不匹配。') }
    else if (t === 'x') value = x
    else if (t && /^\d|^\./.test(t)) value = Number(t)
    else throw new AppError('BUSINESS_RULE', '公式不完整。')
    depth--; return value
  }
  const term = (): number => { let v = atom(); while (tokens[index] === '*' || tokens[index] === '/') { const op = tokens[index++], n = atom(); if (op === '/' && n === 0) throw new AppError('BUSINESS_RULE', '公式不能除以零。'); v = op === '*' ? v * n : v / n }; return v }
  const expression = (): number => { let v = term(); while (tokens[index] === '+' || tokens[index] === '-') { const op = tokens[index++], n = term(); v = op === '+' ? v + n : v - n }; return v }
  const value = expression()
  if (index !== tokens.length || !Number.isFinite(value)) throw new AppError('BUSINESS_RULE', '公式计算结果无效。')
  return value
}
