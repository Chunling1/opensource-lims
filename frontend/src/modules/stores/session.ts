import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { AuthResponse, DataScope } from '@/services/auth'

const emptyScope: DataScope = { department: '', scopeType: 'all', description: '' }

// 会话只保存后端登录接口返回的权限和数据范围，前端不自行决定权限
export const useSessionStore = defineStore('session', () => {
  const account = ref('')
  const userName = ref('')
  const roleKey = ref('')
  const roleName = ref('')
  const homePath = ref('/login')
  const dataScope = ref<DataScope>({ ...emptyScope })
  const permissions = ref<string[]>([])
  const actionPermissions = ref<string[]>([])
  const aiAssistantEnabled = ref(false)
  const aiVoiceEnabled = ref(false)
  const bimCadExperimentEnabled = ref(false)
  const businessReadOnly = ref(false)
  const stageSigning = ref(false)
  const canCorrectBusinessData = ref(false)
  const fullPlatformAuthority = ref(false)
  const deploymentRole = ref<'standard' | 'validation'>('standard')
  const environmentLabel = ref('')
  const externalSideEffectsEnabled = ref(true)

  const permissionSet = computed(() => new Set(permissions.value))
  const actionPermissionSet = computed(() => new Set(actionPermissions.value))
  // Retain the compatibility property; no account can bypass date ordering.
  const canOverrideWorkflowDate = computed(() => false)
  const can = (permission: string) => permissionSet.value.has(permission)
  const canAction = (permission: string) =>
    !businessReadOnly.value && (actionPermissionSet.value.has(permission) || (canCorrectBusinessData.value && /^quality\.(standard|master_standard|equipment|personnel)\.update$/.test(permission)))

  function applyAuth(payload: AuthResponse) {
    account.value = payload.account
    userName.value = payload.userName
    roleKey.value = payload.roleKey
    roleName.value = payload.roleName
    homePath.value = payload.homePath
    dataScope.value = { ...payload.dataScope }
    permissions.value = [...payload.permissions]
    actionPermissions.value = [...payload.actionPermissions]
    aiAssistantEnabled.value = Boolean(payload.features?.aiAssistant)
    aiVoiceEnabled.value = Boolean(payload.features?.aiVoice)
    bimCadExperimentEnabled.value = Boolean(payload.features?.bimCadExperiment)
    businessReadOnly.value = Boolean(payload.features?.businessReadOnly)
    stageSigning.value = Boolean(payload.features?.stageSigning)
    canCorrectBusinessData.value = Boolean(payload.features?.businessDataCorrection)
    fullPlatformAuthority.value = Boolean(payload.features?.fullPlatformAuthority)
    deploymentRole.value = payload.features?.deploymentRole ?? 'standard'
    environmentLabel.value = payload.features?.environmentLabel ?? ''
    externalSideEffectsEnabled.value = payload.features?.externalSideEffectsEnabled ?? true
  }

  function clear() {
    account.value = ''
    userName.value = ''
    roleKey.value = ''
    roleName.value = ''
    homePath.value = '/login'
    dataScope.value = { ...emptyScope }
    permissions.value = []
    actionPermissions.value = []
    aiAssistantEnabled.value = false
    aiVoiceEnabled.value = false
    bimCadExperimentEnabled.value = false
    businessReadOnly.value = false
    stageSigning.value = false
    canCorrectBusinessData.value = false
    fullPlatformAuthority.value = false
    deploymentRole.value = 'standard'
    environmentLabel.value = ''
    externalSideEffectsEnabled.value = true
  }

  return {
    account,
    userName,
    roleKey,
    roleName,
    homePath,
    dataScope,
    permissions,
    actionPermissions,
    aiAssistantEnabled,
    aiVoiceEnabled,
    bimCadExperimentEnabled,
    businessReadOnly,
    stageSigning,
    canCorrectBusinessData,
    fullPlatformAuthority,
    deploymentRole,
    environmentLabel,
    externalSideEffectsEnabled,
    canOverrideWorkflowDate,
    can,
    canAction,
    applyAuth,
    clear,
  }
})
