// Host-provided transport; keep each mounted challenge bound to its account and abort signal.
import { inject } from 'vue'
export function useCaptchaApi() {
  const api = inject('aj-captcha-api')
  if (!api) throw new Error('AJ-Captcha transport is required')
  return api
}
