<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthLayout from '../../components/auth/AuthLayout.vue'
import PasswordField from '../../components/auth/PasswordField.vue'
import AjCaptcha from '../../components/auth/AjCaptcha.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import { AuthRequestError, queryLoginState } from '../../services/auth/authApi'
import { signIn, rememberedAccount, changeAccountPassword } from '../../services/auth/authApi'
import { PlatformError } from '../../services/platform/http'
import { normalizeError } from '../../services/common/errors'
import { validateNewPassword } from '../../services/auth/passwordPolicy'
import { loginReturn } from '../../router/modules/auth'
defineProps<{ sessionExpired?: boolean }>()
const route = useRoute(), router = useRouter()
const isDemoMode = import.meta.env.VITE_DEMO_MODE === '1'
const demoAccounts = [
  { account: 'admin', password: 'LimsDemo!2026', label: '系统管理员', desc: '组织 / 标准库 / 仪器 / 检测方案' },
  { account: 'sim_registrar', password: 'SimRole!2026', label: '张受理 · 受理与样品员', desc: '委托登记 / 双序列收样 / 合同评审' },
  { account: 'sim_tester', password: 'SimRole!2026', label: '李主检 · 主检工程师', desc: '不可用仪器拦截 / 数据录入 / 报告' },
  { account: 'sim_approver', password: 'SimRole!2026', label: '王审签 · 审核批准签发', desc: '审核 / 批准 / 签发 / 归档发放' },
] as const
async function quickDemoLogin(item: (typeof demoAccounts)[number]) {
  if (busy.value) return
  account.value = item.account
  password.value = item.password
  await nextTick()
  await submit()
}
const account = ref(rememberedAccount()), password = ref(''), remember = ref(!!account.value), busy = ref(false)
const mustChange = ref(false), newPassword = ref(''), confirmation = ref('')
const errors = ref<Record<string, string>>({}), message = ref('')
const captchaRequired = ref(false), captchaProof = ref(''), captchaOpen = ref(false), checkingAccount = ref(false)
let stateRequest: AbortController | undefined, expiry: ReturnType<typeof setTimeout> | undefined
let resumeLogin = false, disposed = false
function resetProof() { clearTimeout(expiry); captchaProof.value = ''; delete errors.value.captcha }
function openCaptcha(resume = false) { resetProof(); resumeLogin = resume; captchaOpen.value = true }
function closeCaptcha() {
  if (!captchaOpen.value) return
  captchaOpen.value = false; resumeLogin = false; resetProof()
}
function verified(proof: string, expiresAt: number) {
  if (!captchaOpen.value) return
  captchaProof.value = proof; delete errors.value.captcha
  expiry = setTimeout(resetProof, Math.max(0, expiresAt - Date.now()))
  const resume = resumeLogin
  resumeLogin = false; captchaOpen.value = false
  if (resume) void submit()
}
watch(account, () => {
  mustChange.value = false; captchaRequired.value = false; closeCaptcha(); resetProof(); errors.value = {}; message.value = ''
}, { flush: 'sync' })
watch([password, newPassword, confirmation], resetProof)
onBeforeUnmount(() => { disposed = true; clearTimeout(expiry); stateRequest?.abort() })
async function submit() {
  if (busy.value || captchaOpen.value) return
  errors.value = {}; message.value = ''
  if (!account.value.trim()) errors.value.account = '请输入账号。'
  if (!password.value) errors.value.password = '请输入密码。'
  if (Object.keys(errors.value).length) { await focusError(); return }
  busy.value = true
  try {
    if (mustChange.value) validateNewPassword(newPassword.value, confirmation.value)
    stateRequest = new AbortController(); checkingAccount.value = true
    const state = await queryLoginState(account.value.trim(), stateRequest.signal)
    if (disposed) return
    checkingAccount.value = false; captchaRequired.value = state.captchaRequired || mustChange.value
    if (captchaRequired.value && !captchaProof.value) { openCaptcha(true); return }
    if (mustChange.value) {
      await changeAccountPassword(account.value, password.value, newPassword.value, confirmation.value, captchaProof.value)
      password.value = ''; newPassword.value = ''; confirmation.value = ''; mustChange.value = false; resetProof()
      message.value = '密码已修改，请使用新密码登录。'; return
    }
    await signIn(account.value, password.value, remember.value, captchaProof.value || undefined)
    password.value = ''; await router.replace(loginReturn(route.query.redirect))
  }
  catch (cause) {
    if (disposed) return
    if (cause instanceof PlatformError && cause.platformCode === 3) mustChange.value = true
    if (cause instanceof PlatformError && cause.platformCode === 4) captchaRequired.value = true
    const error = normalizeError(cause)
    if (error.fieldErrors) errors.value = error.fieldErrors; else message.value = error.message
    resetProof()
    if (cause instanceof AuthRequestError && cause.captchaRequired !== undefined) captchaRequired.value = cause.captchaRequired
    if (captchaRequired.value && error.fieldErrors?.captcha) openCaptcha(true)
  }
  finally { busy.value = false; checkingAccount.value = false; if (!captchaOpen.value && !disposed) await focusError() }
}
async function focusError() { await nextTick(); document.querySelector<HTMLElement>('input[aria-invalid="true"]')?.focus() }
</script>
<template>
  <AuthLayout :title="mustChange ? '首次登录修改密码' : '用户登录'" :inert="captchaOpen">
    <p v-if="route.query.changed === '1'" class="alert alert-success" role="status">密码已修改，请使用新密码登录。</p>
    <div v-if="message || sessionExpired" class="alert alert-warning" role="alert">{{ message || '登录已失效，请重新登录。重新打开报告后，请核对上次操作是否保存或提交。' }}</div>
    <form novalidate @submit.prevent="submit">
      <div class="mb-3"><label for="login-account" class="form-label">账号</label><input id="login-account" v-model="account" class="form-control" :class="{ 'is-invalid': errors.account }" autocomplete="username" maxlength="128" :disabled="busy" :aria-invalid="!!errors.account" :aria-describedby="errors.account ? 'login-account-error' : undefined" /><div v-if="errors.account" id="login-account-error" class="invalid-feedback" role="alert">{{ errors.account }}</div></div>
      <PasswordField id="login-password" v-model="password" :label="mustChange ? '原密码（当前初始密码）' : '密码'" :error="mustChange ? errors.oldPassword || errors.password : errors.password" :disabled="busy">
        <template #label-action><RouterLink :to="{ path: '/forgot-password', query: { redirect: loginReturn(route.query.redirect) } }" class="text-muted">忘记密码？</RouterLink></template>
      </PasswordField>
      <template v-if="mustChange">
        <p class="alert alert-info">首次登录需修改密码。新密码须为 8–128 位，包含大小写字母、数字和特殊字符（如 !、@、#）。</p>
        <PasswordField id="new-password" v-model="newPassword" label="新密码" autocomplete="new-password" :error="errors.newPassword" :disabled="busy" />
        <PasswordField id="confirm-password" v-model="confirmation" label="确认新密码" autocomplete="new-password" :error="errors.confirmation" :disabled="busy" />
      </template>
      <div v-if="captchaRequired" class="mb-3" data-testid="captcha-entry">
        <button type="button" class="btn btn-light w-100" :class="{ 'text-success': captchaProof }" :disabled="busy || !!captchaProof" aria-haspopup="dialog" @click="openCaptcha()"><i :class="captchaProof ? 'ti ti-circle-check' : 'ti ti-shield-check'" class="me-1" aria-hidden="true"></i>{{ captchaProof ? '验证通过' : '点击完成安全验证' }}</button>
      </div>
      <div class="form-check"><input id="remember-account" v-model="remember" class="form-check-input" type="checkbox" :disabled="busy" /><label class="form-check-label" for="remember-account">记住账号</label></div>
      <div class="mt-4"><button type="submit" class="btn btn-success w-100" :disabled="busy">{{ checkingAccount ? '正在检查登录状态…' : busy ? '正在提交…' : mustChange ? '修改密码' : '登录' }}</button></div>
    </form>
    <div v-if="isDemoMode && !mustChange" class="mt-4 pt-3 border-top">
      <div class="d-flex align-items-center justify-content-between mb-2">
        <span class="fw-semibold small text-body">在线体验 · 一键角色登录</span>
        <span class="badge bg-azure-lt text-azure">每 2 小时自动重置</span>
      </div>
      <div class="d-grid gap-2">
        <button v-for="item in demoAccounts" :key="item.account" type="button" class="btn btn-outline-primary btn-sm text-start d-flex justify-content-between align-items-center" :disabled="busy" @click="quickDemoLogin(item)">
          <span><strong>{{ item.label }}</strong><small class="d-block text-muted fw-normal">{{ item.desc }}</small></span>
          <span class="badge bg-light text-dark ms-2">{{ item.account }}</span>
        </button>
      </div>
      <p class="text-muted small mt-2 mb-0">当前为 Open-LIMS 公共在线体验环境，请勿上传真实敏感文件。</p>
    </div>
  </AuthLayout>
  <BootstrapModal :open="captchaOpen" title="安全验证" compact scrollable @close="closeCaptcha">
    <AjCaptcha v-if="captchaOpen" :account="account.trim()" @reset="resetProof" @verified="verified" />
  </BootstrapModal>
</template>
