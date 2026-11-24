import { AppError } from '../common/errors'

export function validateNewPassword(password: string, confirmation: string) {
  const missing = [
    ...(password.length < 8 || password.length > 128 ? ['8–128 位'] : []),
    ...(!/[A-Z]/.test(password) ? ['大写字母'] : []),
    ...(!/[a-z]/.test(password) ? ['小写字母'] : []),
    ...(!/[0-9]/.test(password) ? ['数字'] : []),
    // Same ASCII punctuation set as Python string.punctuation, including !.
    ...(!/[\x21-\x2f\x3a-\x40\x5b-\x60\x7b-\x7e]/.test(password) ? ['特殊字符（如 !、@、#）'] : []),
  ]
  if (missing.length) {
    const message = `新密码须包含或满足：${missing.join('、')}。`
    throw new AppError('VALIDATION', message, { fieldErrors: { newPassword: message } })
  }
  if (password !== confirmation) throw new AppError('VALIDATION', '两次输入的新密码不一致。', { fieldErrors: { confirmation: '两次输入的新密码不一致。' } })
}
