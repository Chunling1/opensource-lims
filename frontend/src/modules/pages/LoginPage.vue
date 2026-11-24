<template>
  <main >
    <div  />
    <header >
      <div class="mb-3">
        <span class="fw-bold fs-4">LIMS 实验室信息管理系统</span>
        <span  />
        <img src="@/assets/favicon.svg" alt="LIMS"  />
      </div>
      <span >检测业务管理平台</span>
    </header>

    <section >
      <span >Inspection Management Platform</span>
      <h1 class="h5 mb-3">LIMS 实验室信息管理系统</h1>
      <p>检测业务管理、网上委托、报告流转、质量体系与统计分析一体化平台</p>
      <div class="row g-3">
        <div class="col-12 col-md-6" v-for="item in features" :key="item.title">
          <strong>{{ item.title }}</strong>
          <span>{{ item.text }}</span>
        </div>
      </div>
    </section>

    <el-card shadow="never" >
      <template #header>
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
          <div>
            <strong>账号登录</strong>
            <span>使用院内账号进入系统</span>
          </div>
          <el-tag type="success" size="small">安全入口</el-tag>
        </div>
      </template>

      <el-alert
        v-if="deploymentRole === 'validation'"
        
        type="warning"
        :closable="false"
        show-icon
        title="隔离测试平台"
        :description="`${environmentLabel || '验证环境'}：本平台产生的业务数据仅用于流程验证，不会同步或回灌原平台。`"
      />

      <el-form v-if="!changing" label-position="top"  @submit.prevent>
        <el-form-item label="账号">
          <el-input v-model="account" :disabled="loading" size="large" placeholder="请输入账号" :prefix-icon="User" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" :disabled="loading" size="large" type="password" placeholder="请输入密码" :prefix-icon="Lock" show-password @keyup.enter="login" />
        </el-form-item>

        <CaptchaInput />
        <div >
          <el-checkbox v-model="remember">记住账号</el-checkbox>
          <el-button link @click="forgot">忘记密码</el-button>
        </div>

        <el-button  type="primary" size="large" :loading="loading"  :disabled="loading" @click="login">登录系统</el-button>
        <el-alert v-if="lockSeconds > 0" type="warning" :closable="false" :title="`账号锁定剩余 ${Math.floor(lockSeconds / 60)} 分 ${lockSeconds % 60} 秒；管理员重置后可立即重试。`" />
      </el-form>

      <el-form v-else label-position="top"  @submit.prevent>
        <el-alert type="warning" :closable="false" show-icon class="text-muted small" :title="cpTitle" />
        <el-form-item label="账号"><el-input v-model="account" size="large" disabled :prefix-icon="User" /></el-form-item>
        <el-form-item label="原密码（或临时密码）">
          <el-input v-model="oldPassword" size="large" type="password" placeholder="请输入原密码" :prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item label="新密码（至少 8 位，含大小写英文、数字和特殊字符）">
          <el-input v-model="newPassword" size="large" type="password" placeholder="请输入新密码" :prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="confirmPassword" size="large" type="password" placeholder="再次输入新密码" :prefix-icon="Lock" show-password @keyup.enter="submitChange" />
        </el-form-item>
        <CaptchaInput />
        <el-button  type="primary" size="large" :loading="loading" @click="submitChange">重置密码并返回登录</el-button>
        <el-button link  @click="changing = false">返回登录</el-button>
      </el-form>

      <div >
        <span>建议使用最新版 Chrome / Edge 浏览器</span>
        <span>技术支持：信息管理员</span>
      </div>
    </el-card>

    <footer >© 2026 LIMS 实验室信息管理系统</footer>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useLoginCaptcha, strongPassword } from '@/services/loginSecurityUi'
import { useRouter } from 'vue-router'
import { Lock, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { gsap } from 'gsap'
import loginBackground from '@/assets/login-building.jpg'
import { changePasswordRequest, fetchPublicSystemStatus, loginRequest } from '@/services/auth'
import { checkForBuildUpdate } from '@/services/buildVersion'
import { ApiError } from '@/services/http'
import { useLoginLock } from '@/composables/loginLock'
import { useSessionStore } from '@/stores/session'

const captcha = useLoginCaptcha()
const CaptchaInput = captcha.Component
const router = useRouter()
const session = useSessionStore()
const rememberedAccount = localStorage.getItem('hn_last_account') ?? ''
const account = ref(rememberedAccount)
const password = ref('')
const loginLock = useLoginLock(account)
const lockSeconds = loginLock.seconds
const remember = ref(Boolean(rememberedAccount))
const loading = ref(false)
const deploymentRole = ref<'standard' | 'validation'>('standard')
const environmentLabel = ref('')
// 首次登录/找回 → 改密
const changing = ref(false)
const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const cpTitle = ref('首次登录，请重置密码后再登录')
const features = [
  { title: '检测闭环', text: '委托、样品、检测、报告全流程管理' },
  { title: '统一待办', text: '审批、预警、通知集中处理' },
  { title: '接口集成', text: '外部ERP、短信、Word 模板、自动采集' },
]

onMounted(() => {
  void checkForBuildUpdate()
  void loadPublicSystemStatus()
  document.documentElement.style.setProperty('--login-bg', `url(${loginBackground})`)
  gsap.fromTo('.login-logo-bar', { opacity: 0, y: -10 }, { opacity: 1, y: 0, duration: 0.45, ease: 'power2.out' })
  gsap.fromTo('.login-copy > *', { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.45, stagger: 0.08, ease: 'power2.out' })
  gsap.fromTo('.login-card', { opacity: 0, x: 24 }, { opacity: 1, x: 0, duration: 0.45, ease: 'power2.out' })
})

async function loadPublicSystemStatus() {
  try {
    const status = await fetchPublicSystemStatus()
    deploymentRole.value = status.deploymentRole
    environmentLabel.value = status.environmentLabel
  } catch {
    deploymentRole.value = 'standard'
    environmentLabel.value = ''
  }
}

function forgot() {
  ElMessage.info('忘记密码请联系系统管理员重置，重置后下次登录需修改密码')
}

async function login() {
  if (loading.value) return
  loading.value = true
  try {
    // 长时间停留在登录页后仍需核对版本，但版本请求与登录请求并行，
    // 避免把一次公网往返时间串行叠加到登录等待中。
    const buildCheck = checkForBuildUpdate()
    const auth = await loginRequest(account.value, password.value, captcha.values())
    if (await buildCheck) return
    if (remember.value) localStorage.setItem('hn_last_account', account.value.trim())
    else localStorage.removeItem('hn_last_account')
    loginLock.clear()
    session.applyAuth(auth)
    router.push(session.homePath)
  } catch (error) {
    if (error instanceof ApiError && String(error.code) === '2') {
      const data = error.data as { retryAfterSeconds?: number } | null
      loginLock.lock(Number(data?.retryAfterSeconds || 1800))
      password.value = ''
    }
    // code 3：首次登录需改密 → 切到改密表单
    if (error instanceof ApiError && error.code === 3) {
      changing.value = true
      cpTitle.value = '首次登录，请重置密码后再登录'
      oldPassword.value = password.value
      newPassword.value = ''
      confirmPassword.value = ''
    } else {
      ElMessage.error(error instanceof Error ? error.message : '登录失败')
    }
  } finally {
    await captcha.refresh()
    loading.value = false
  }
}

async function submitChange() {
  if (loading.value) return
  if (newPassword.value !== confirmPassword.value) return ElMessage.warning('两次输入的新密码不一致')
  if (!strongPassword(newPassword.value)) return ElMessage.warning('密码至少 8 位，须包含大写英文、小写英文、数字和特殊字符')
  loading.value = true
  try {
    await changePasswordRequest(account.value, oldPassword.value, newPassword.value, captcha.values())
    ElMessage.success('密码已重置，请用新密码登录')
    changing.value = false
    password.value = ''
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '改密失败')
  } finally {
    await captcha.refresh()
    loading.value = false
  }
}
</script>
