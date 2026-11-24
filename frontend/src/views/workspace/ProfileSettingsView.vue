<script setup lang="ts">
import UserAvatar from '../../components/common/UserAvatar.vue'
import { prepareAvatar } from '../../services/auth/avatar'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { currentActor, refreshIdentity, roleLabels } from '../../stores/session'
import { profile } from '../../services/platform/auth'
import { changeAccountPassword, signOut } from '../../services/auth/authApi'
import { profileService, type PersonalDetails } from '../../services/auth/profileService'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { useFormLeaveGuard } from '../../components/common/useFormLeaveGuard'
import FormLeaveConfirmation from '../../components/common/FormLeaveConfirmation.vue'
import LoadState from '../../components/common/LoadState.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import PasswordField from '../../components/auth/PasswordField.vue'

const route = useRoute(), router = useRouter()
const passwords = ref({ oldPassword: '', password: '', confirmation: '' })
const passwordErrors = ref<Record<string, string>>({}), passwordMessage = ref('')
const savedDraft = ref('')
const assets = `${import.meta.env.BASE_URL}template/assets/images/`
let editingId = currentActor.value.id
const draft = ref<PersonalDetails>({ phone: '', email: '', avatar: '' })
const avatarInput = ref<HTMLInputElement>()
const ready = ref(false), loading = ref(false), busy = ref(false), department = ref(''), tab = ref('details')
const loadError = ref<ErrorValue>(''), error = ref<ErrorValue>(''), success = ref(''), errors = ref<Record<string, string>>({})
const tabs = [{ key: 'details', label: '个人资料' }, { key: 'password', label: '修改密码' }, { key: 'position', label: '岗位信息' }]
const detailsDirty = computed(() => JSON.stringify(draft.value) !== savedDraft.value)
const completeness = computed(() => [currentActor.value.id, currentActor.value.name, currentActor.value.phone, currentActor.value.email].filter(value => value?.trim()).length * 25)
const guard = useFormLeaveGuard(() => ({ details: detailsDirty.value ? draft.value : null, passwords: passwords.value }), () => ready.value, () => busy.value)
watch(() => route.query.tab, value => { tab.value = value === 'password' ? 'password' : 'details' }, { immediate: true })
async function navigateTab(event: KeyboardEvent, index: number) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key) || busy.value) return
  event.preventDefault()
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length
  tab.value = tabs[next]!.key
  await nextTick(); document.getElementById(`profile-settings-tab-${tab.value}`)?.focus()
}
async function savePassword() {
  if (busy.value || detailsDirty.value) return
  busy.value = true; passwordErrors.value = {}; passwordMessage.value = ''
  try {
    await changeAccountPassword(currentActor.value.id, passwords.value.oldPassword, passwords.value.password, passwords.value.confirmation)
    passwords.value = { oldPassword: '', password: '', confirmation: '' }
    guard.commit(); signOut(); busy.value = false
    await router.replace({ path: '/login', query: { changed: '1' } })
  } catch (cause) {
    const issue = normalizeError(cause)
    if (issue.fieldErrors) passwordErrors.value = issue.fieldErrors; else passwordMessage.value = issue.message
  } finally {
    busy.value = false
    await nextTick(); document.querySelector<HTMLElement>('#profile-password-form [aria-invalid="true"]')?.focus()
  }
}
const managedInfo = computed(() => [
  ['人员账号', currentActor.value.id], ['所属部门', department.value], ['岗位', currentActor.value.position],
  ['职务', currentActor.value.jobTitle], ['上岗证号', currentActor.value.certificateNumber],
  ['角色', currentActor.value.roles.map(role => roleLabels[role] || role).join(' / ')],
  ['数据范围', profile.value?.dataScope.description || '未设置'],
])
let disposed = false
onBeforeUnmount(() => { disposed = true })
async function load() {
  loading.value = true; loadError.value = ''
  try {
    await refreshIdentity(true)
    if (disposed) return
    const actor = currentActor.value; editingId = actor.id
    draft.value = { phone: actor.phone || '', email: actor.email || '', avatar: actor.avatar || '' }
    department.value = profile.value?.personal?.departmentName || '未设置'
    savedDraft.value = JSON.stringify(draft.value); ready.value = true; guard.commit()
  } catch (cause) { if (!disposed) loadError.value = normalizeError(cause) }
  finally { if (!disposed) loading.value = false }
}
onMounted(load)
async function changeAvatar(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  if (!file || busy.value) return
  busy.value = true; delete errors.value.avatar; success.value = ''
  try {
    const avatar = await prepareAvatar(file)
    if (!disposed) { draft.value.avatar = avatar; tab.value = 'details' }
  } catch (cause) { if (!disposed) errors.value.avatar = normalizeError(cause).message }
  finally { input.value = ''; if (!disposed) busy.value = false }
}
function resetAvatar() { draft.value.avatar = ''; delete errors.value.avatar; tab.value = 'details' }
async function save() {
  if (busy.value) return
  busy.value = true; errors.value = {}; error.value = ''; success.value = ''
  try {
    draft.value = await profileService.save(editingId, draft.value)
    savedDraft.value = JSON.stringify(draft.value)
    await refreshIdentity()
    success.value = '个人资料已保存。'
  } catch (cause) {
    const issue = normalizeError(cause)
    if (issue.fieldErrors) errors.value = issue.fieldErrors; else error.value = issue
  } finally {
    busy.value = false
    await nextTick(); document.querySelector<HTMLElement>('#personal-details-form [aria-invalid="true"]')?.focus()
  }
}
</script>

<template>
  <section aria-label="编辑个人资料">
    <div class="position-relative mx-n4 mt-n4" aria-hidden="true"><div class="profile-wid-bg profile-setting-img"><img :src="`${assets}profile-bg.jpg`" alt="" class="profile-wid-img" /></div></div>
    <div class="row">
      <aside class="col-xxl-3">
        <div class="card mt-n5"><div class="card-body p-4 text-center"><div class="profile-user position-relative d-inline-block mx-auto mb-4"><UserAvatar :src="ready ? draft.avatar : currentActor.avatar" class="rounded-circle avatar-xl img-thumbnail user-profile-image material-shadow" />
          <input ref="avatarInput" id="profile-avatar-file" type="file" class="profile-img-file-input" accept="image/jpeg,image/png,image/webp" aria-label="选择头像图片" :disabled="!ready || busy" @change="changeAvatar" />
          <button type="button" class="avatar-xs p-0 rounded-circle profile-photo-edit border-0" aria-label="更换头像" :disabled="!ready || busy" :aria-describedby="errors.avatar ? 'profile-avatar-error' : undefined" @click="avatarInput?.click()"><span class="avatar rounded-circle bg-light text-body material-shadow"><i class="ti ti-camera" aria-hidden="true"></i></span></button></div><p v-if="errors.avatar" id="profile-avatar-error" class="text-danger small" role="alert">{{ errors.avatar }}</p><button v-if="draft.avatar" type="button" class="btn btn-link btn-sm p-0 mb-3" :disabled="busy" @click="resetAvatar">恢复默认头像</button><h1 class="fs-4 mb-1">{{ currentActor.name }}</h1><p class="text-muted mb-0">{{ currentActor.roles.map(role => roleLabels[role] || role).join(' / ') }}</p></div></div>
        <div class="card"><div class="card-body"><h2 class="card-title mb-5">资料完整度</h2><div class="progress animated-progress custom-progress progress-label"><div class="progress-bar" :class="[`w-${completeness}`, completeness === 100 ? 'bg-success' : 'bg-warning']" role="progressbar" :aria-valuenow="completeness" aria-valuemin="0" aria-valuemax="100" aria-label="资料完整度"><div class="label">{{ completeness }}%</div></div></div></div></div>
        <div class="card"><div class="card-body"><h2 class="card-title mb-3">资料维护</h2><p class="text-muted">完善联系方式，便于检测业务协作。</p><p class="text-muted mb-0">姓名、部门、岗位及上岗资质由管理员维护。</p></div></div>
      </aside>
      <div class="col-xxl-9">
        <div class="card mt-xxl-n5"><div class="card-header"><ul class="nav nav-tabs-custom rounded card-header-tabs border-bottom-0" role="tablist" aria-label="编辑资料栏目"><li v-for="(item, index) in tabs" :key="item.key" class="nav-item" role="presentation"><button :id="`profile-settings-tab-${item.key}`" type="button" class="nav-link" :class="{ active: tab === item.key }" role="tab" :aria-selected="tab === item.key" :aria-controls="`profile-settings-panel-${item.key}`" :tabindex="tab === item.key ? 0 : -1" :disabled="busy" @click="tab = item.key" @keydown="navigateTab($event, index)">{{ item.label }}</button></li></ul></div>
          <div class="card-body p-4">
            <LoadState :loading="loading" :error="loadError" @retry="load" />
            <template v-if="ready">
              <ErrorNotice :error="error" />
              <div v-show="tab === 'details'" id="profile-settings-panel-details" role="tabpanel" aria-labelledby="profile-settings-tab-details">
                <form id="personal-details-form" novalidate @submit.prevent="save">
                  <div class="row g-3">
                    <div class="col-lg-6"><label for="profile-name" class="form-label">姓名</label><input id="profile-name" :value="currentActor.name" class="form-control" disabled /></div>
                    <div class="col-lg-6"><label for="profile-account" class="form-label">人员账号</label><input id="profile-account" class="form-control" :value="currentActor.id" disabled /></div>
                    <div class="col-lg-6"><label for="profile-phone" class="form-label">联系电话</label><input id="profile-phone" v-model="draft.phone" type="tel" class="form-control" :class="{ 'is-invalid': errors.phone }" :disabled="busy" maxlength="30" autocomplete="tel" :aria-invalid="!!errors.phone" :aria-describedby="errors.phone ? 'profile-phone-error' : undefined" /><div v-if="errors.phone" id="profile-phone-error" class="invalid-feedback">{{ errors.phone }}</div></div>
                    <div class="col-lg-6"><label for="profile-email" class="form-label">电子邮箱</label><input id="profile-email" v-model="draft.email" type="email" class="form-control" :class="{ 'is-invalid': errors.email }" :disabled="busy" maxlength="254" autocomplete="email" :aria-invalid="!!errors.email" :aria-describedby="errors.email ? 'profile-email-error' : undefined" /><div v-if="errors.email" id="profile-email-error" class="invalid-feedback">{{ errors.email }}</div></div>
                    <div class="col-12"><div class="d-flex flex-wrap gap-2 justify-content-end mt-2"><button type="submit" class="btn btn-primary" :disabled="busy">{{ busy ? '正在保存…' : '保存修改' }}</button><RouterLink to="/profile" class="btn btn-success-lt" :class="{ disabled: busy }" :aria-disabled="busy">返回个人资料</RouterLink></div></div>
                  </div>
                </form>
              </div>
              <div v-show="tab === 'position'" id="profile-settings-panel-position" role="tabpanel" aria-labelledby="profile-settings-tab-position"><div class="row g-3"><div v-for="([label, value], index) in managedInfo" :key="label" class="col-lg-6"><label :for="`profile-managed-${index}`" class="form-label">{{ label }}</label><input :id="`profile-managed-${index}`" :value="value || '未填写'" class="form-control" disabled /></div></div><p class="text-muted mt-3 mb-0">以上信息需通过人员与权限管理流程调整。</p></div>
              <div v-show="tab === 'password'" id="profile-settings-panel-password" role="tabpanel" aria-labelledby="profile-settings-tab-password">
                <p v-if="passwordMessage" class="alert alert-warning" role="alert">{{ passwordMessage }}</p>
                <div v-if="detailsDirty" class="alert alert-info">个人资料有未保存的修改，请先保存。<button type="button" class="btn btn-link p-0 ms-2" @click="tab = 'details'">返回个人资料表单</button></div>
                <form id="profile-password-form" novalidate @submit.prevent="savePassword">
                  <div class="row g-2">
                    <div class="col-lg-4"><PasswordField id="old-password" v-model="passwords.oldPassword" label="原密码" :error="passwordErrors.oldPassword" :disabled="busy" /></div>
                    <div class="col-lg-4"><PasswordField id="new-password" v-model="passwords.password" label="新密码" autocomplete="new-password" :error="passwordErrors.newPassword" :disabled="busy" /></div>
                    <div class="col-lg-4"><PasswordField id="confirm-password" v-model="passwords.confirmation" label="确认密码" autocomplete="new-password" :error="passwordErrors.confirmation" :disabled="busy" /></div>
                    <div class="col-lg-12"><div class="mb-3"><RouterLink to="/forgot-password" class="link-primary text-decoration-underline">忘记密码？</RouterLink><p class="text-muted small mt-2 mb-0">新密码须为 8–128 位，包含大小写字母、数字和特殊字符，修改成功后重新登录。</p></div></div>
                    <div class="col-lg-12"><div class="text-end"><button type="submit" class="btn btn-success" :disabled="busy || detailsDirty">{{ busy ? '正在保存…' : '保存并重新登录' }}</button></div></div>
                  </div>
                </form>
                <div class="mt-4 mb-3 border-bottom pb-2"><h2 class="card-title">当前登录</h2></div>
                <div class="d-flex align-items-center gap-3"><div class="flex-shrink-0 avatar-sm"><div class="avatar bg-light text-primary rounded-3 fs-3 material-shadow"><i class="ti ti-device-desktop" aria-hidden="true"></i></div></div><div class="flex-grow-1"><h3 class="fs-5">当前浏览器标签页</h3><p class="text-muted mb-0">{{ currentActor.id }} · 密码修改后需重新登录</p></div><button type="button" class="btn btn-link flex-shrink-0 text-nowrap" @click="signOut(); router.replace('/login')">退出登录</button></div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </section>
  <TemplateToast :message="success" tone="success" auto-show />
  <FormLeaveConfirmation :guard="guard" />
</template>
