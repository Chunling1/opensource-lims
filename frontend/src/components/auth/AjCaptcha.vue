<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, provide, ref } from 'vue'
import NativeVerify from '../../../vendor/aj-captcha/components/Verify.vue'
import { checkCaptcha, getCaptcha } from '../../services/auth/authApi'
import { normalizeError } from '../../services/common/errors'
import type { CaptchaType } from '../../types/auth'
const props = defineProps<{ account: string }>()
const emit = defineEmits<{ verified: [proof: string, expiresAt: number]; reset: [] }>()
// Choose once per mounted dialog; refresh/retry/resize must not change the task.
const captchaType: CaptchaType = crypto.getRandomValues(new Uint32Array(1))[0]! % 2 === 0 ? 'blockPuzzle' : 'clickWord'
const width = ref(Math.min(310, Math.max(220, window.innerWidth - 72)))
const imgSize = computed(() => ({ width: `${width.value}px`, height: `${width.value / 2}px` }))
const native = ref<{ instance?: { refresh: () => void } }>()
let request = new AbortController(), expiry: ReturnType<typeof setTimeout> | undefined
let proofExpiresAt = 0, disposed = false
function resize() {
  const next = Math.min(310, Math.max(220, window.innerWidth - 72))
  if (next !== width.value) { request.abort(); request = new AbortController(); clearTimeout(expiry); emit('reset'); width.value = next }
}
function failure(error: unknown) { return { repCode: 'FAILED', repMsg: normalizeError(error).message } }
provide('aj-captcha-api', {
  async reqGet() {
    clearTimeout(expiry); proofExpiresAt = 0; emit('reset')
    request.abort(); request = new AbortController()
    try {
      const repData = await getCaptcha(props.account, captchaType, request.signal)
      if (!disposed) expiry = setTimeout(() => { emit('reset'); native.value?.instance?.refresh() }, Math.max(0, repData.expiresAt - Date.now()))
      return { repCode: '0000', repData }
    } catch (error) { return failure(error) }
  },
  async reqCheck(data: { token: string; pointJson: string }) {
    clearTimeout(expiry)
    try {
      const repData = await checkCaptcha(props.account, data.token, data.pointJson, captchaType, request.signal)
      proofExpiresAt = repData.expiresAt
      return { repCode: '0000', repData }
    } catch (error) { return failure(error) }
  },
})
function success(value: { captchaVerification: string }) {
  if (!disposed && proofExpiresAt > Date.now()) emit('verified', value.captchaVerification, proofExpiresAt)
}
onMounted(() => window.addEventListener('resize', resize))
onBeforeUnmount(() => { disposed = true; request.abort(); clearTimeout(expiry); window.removeEventListener('resize', resize) })
</script>
<template>
  <div class="d-flex justify-content-center" data-testid="login-captcha" :data-captcha-type="captchaType">
    <NativeVerify class="text-body py-1" :key="width" ref="native" :captcha-type="captchaType" mode="fixed" :v-space="8" :img-size="imgSize" @success="success" @error="emit('reset')" />
  </div>
</template>
