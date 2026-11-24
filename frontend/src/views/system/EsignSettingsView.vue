<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { platformRequest } from '../../services/platform/http'
import { normalizeError } from '../../services/common/errors'

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const hasAppSecret = ref(false)
const appSecretMasked = ref('')

const form = reactive({
  enabled: false,
  requiredForIssuance: false,
  baseUrl: 'https://openapi.esign.cn',
  appId: '',
  appSecret: '',
  orgId: '',
  orgName: '',
  orgSealId: '',
  orgAutosignEnabled: false,
  callbackUrl: '',
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await platformRequest<Record<string, unknown>>('/api/system/esign-config')
    form.enabled = Boolean(data.enabled)
    form.requiredForIssuance = Boolean(data.requiredForIssuance)
    form.baseUrl = String(data.baseUrl || 'https://openapi.esign.cn')
    form.appId = String(data.appId || '')
    form.appSecret = ''
    hasAppSecret.value = Boolean(data.hasAppSecret)
    appSecretMasked.value = String(data.appSecretMasked || '')
    form.orgId = String(data.orgId || '')
    form.orgName = String(data.orgName || '')
    form.orgSealId = String(data.orgSealId || '')
    form.orgAutosignEnabled = Boolean(data.orgAutosignEnabled)
    form.callbackUrl = String(data.callbackUrl || '')
  } catch (e) {
    error.value = normalizeError(e).message
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    const data = await platformRequest<Record<string, unknown>>('/api/system/esign-config', {
      method: 'PUT',
      body: JSON.stringify({ ...form }),
    })
    hasAppSecret.value = Boolean(data.hasAppSecret)
    appSecretMasked.value = String(data.appSecretMasked || '')
    form.appSecret = ''
    notice.value = '电子签章配置已保存并立即生效。'
  } catch (e) {
    error.value = normalizeError(e).message
  } finally {
    saving.value = false
  }
}

onMounted(() => { void load() })
</script>

<template>
  <div class="page-header d-print-none mb-3">
    <div class="row align-items-center">
      <div class="col">
        <div class="page-pretitle">系统管理</div>
        <h2 class="page-title">电子签章配置（e签宝）</h2>
      </div>
    </div>
  </div>

  <div v-if="error" class="alert alert-danger" role="alert">{{ error }}</div>
  <div v-if="notice" class="alert alert-success" role="status">{{ notice }}</div>

  <div class="card">
    <div class="card-header">
      <h3 class="card-title">签章服务与印章参数</h3>
      <div class="card-actions">
        <span class="badge" :class="form.enabled ? 'bg-success-lt text-success' : 'bg-secondary-lt text-secondary'">
          {{ form.enabled ? '已启用线上签章' : '当前为线下签章归档模式' }}
        </span>
      </div>
    </div>
    <form class="card-body" @submit.prevent="save">
      <div v-if="loading" class="text-secondary py-4 text-center">
        <span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>正在加载配置…
      </div>
      <template v-else>
        <div class="row g-3">
          <div class="col-md-6">
            <label class="form-check form-switch">
              <input v-model="form.enabled" class="form-check-input" type="checkbox" role="switch" />
              <span class="form-check-label fw-medium">启用线上电子签章（关闭时直接走线下签章扫描件归档发放）</span>
            </label>
          </div>
          <div class="col-md-6">
            <label class="form-check form-switch">
              <input v-model="form.requiredForIssuance" class="form-check-input" type="checkbox" role="switch" :disabled="!form.enabled" />
              <span class="form-check-label">签发归档前强制完成电子签署</span>
            </label>
          </div>

          <div class="col-md-6">
            <label for="esign-base-url" class="form-label">e签宝接口地址</label>
            <input id="esign-base-url" v-model="form.baseUrl" type="url" class="form-control" placeholder="https://openapi.esign.cn" />
          </div>
          <div class="col-md-6">
            <label for="esign-callback-url" class="form-label">回调 / 跳转地址</label>
            <input id="esign-callback-url" v-model="form.callbackUrl" type="url" class="form-control" placeholder="https://your-domain.com/api/esign/callback" />
          </div>

          <div class="col-md-6">
            <label for="esign-app-id" class="form-label">AppID</label>
            <input id="esign-app-id" v-model="form.appId" type="text" class="form-control" placeholder="填写企业应用 AppID" />
          </div>
          <div class="col-md-6">
            <label for="esign-app-secret" class="form-label">
              AppSecret
              <span v-if="hasAppSecret" class="text-secondary small ms-1">（已配置：{{ appSecretMasked }}，留空则保持不变）</span>
            </label>
            <input id="esign-app-secret" v-model="form.appSecret" type="password" class="form-control" autocomplete="new-password" placeholder="输入新的 AppSecret" />
          </div>

          <div class="col-md-4">
            <label for="esign-org-name" class="form-label">签章机构名称</label>
            <input id="esign-org-name" v-model="form.orgName" type="text" class="form-control" placeholder="例如：XX检测实验室" />
          </div>
          <div class="col-md-4">
            <label for="esign-org-id" class="form-label">机构账号 ID（OrgId）</label>
            <input id="esign-org-id" v-model="form.orgId" type="text" class="form-control" placeholder="e签宝企业 orgId" />
          </div>
          <div class="col-md-4">
            <label for="esign-seal-id" class="form-label">印章 ID（SealId）</label>
            <input id="esign-seal-id" v-model="form.orgSealId" type="text" class="form-control" placeholder="指定检测专用章/公章 ID" />
          </div>

          <div class="col-12">
            <label class="form-check form-switch">
              <input v-model="form.orgAutosignEnabled" class="form-check-input" type="checkbox" role="switch" :disabled="!form.enabled" />
              <span class="form-check-label">签发时允许自动加盖机构印章（需 e签宝开通静默签署授权）</span>
            </label>
          </div>
        </div>

        <div class="mt-4 d-flex gap-2">
          <button type="submit" class="btn btn-primary" :disabled="saving">
            <i class="ti ti-device-floppy me-1" aria-hidden="true"></i>{{ saving ? '正在保存…' : '保存签章配置' }}
          </button>
          <button type="button" class="btn btn-outline-secondary" :disabled="saving" @click="load">重置</button>
        </div>
      </template>
    </form>
  </div>
</template>
