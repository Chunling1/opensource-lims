<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getSessionToken, platformRequest } from '../../services/platform/http'
import { normalizeError } from '../../services/common/errors'

interface TemplateItem {
  id: number
  kind: 'commission' | 'report'
  name: string
  fileName: string
  placeholders: string[]
  fieldMapping: Record<string, string>
  isActive: boolean
  createdBy: string
  updatedAt: string
}

interface SystemField {
  key: string
  label: string
}

const loading = ref(true)
const uploading = ref(false)
const error = ref('')
const notice = ref('')
const items = ref<TemplateItem[]>([])
const systemFields = ref<SystemField[]>([])
const editingId = ref<number | null>(null)
const draftMapping = ref<Record<string, string>>({})

const uploadKind = ref<'commission' | 'report'>('report')
const uploadName = ref('')
const uploadFile = ref<File | null>(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await platformRequest<{ items: TemplateItem[]; systemFields: SystemField[] }>('/api/system/templates')
    items.value = res.items || []
    systemFields.value = res.systemFields || []
  } catch (e) {
    error.value = normalizeError(e).message
  } finally {
    loading.value = false
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] || null
  uploadFile.value = file
  if (file && !uploadName.value.trim()) {
    uploadName.value = file.name.replace(/\.docx$/i, '')
  }
}

async function handleUpload() {
  if (!uploadFile.value) {
    error.value = '请先选择 .docx 模板文件'
    return
  }
  uploading.value = true
  error.value = ''
  notice.value = ''
  try {
    const fd = new FormData()
    fd.append('kind', uploadKind.value)
    fd.append('name', uploadName.value.trim() || uploadFile.value.name)
    fd.append('file', uploadFile.value)
    const token = getSessionToken()
    const resp = await fetch('/api/system/templates', {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    })
    const payload = await resp.json()
    if (!resp.ok || payload.code !== 0) {
      throw new Error(payload.message || '上传失败')
    }
    uploadName.value = ''
    uploadFile.value = null
    notice.value = '模板已上传并自动提取占位符，请在下方完成字段映射。'
    await load()
  } catch (e) {
    error.value = normalizeError(e).message
  } finally {
    uploading.value = false
  }
}

function startMapping(item: TemplateItem) {
  editingId.value = item.id
  draftMapping.value = { ...item.fieldMapping }
}

async function saveMapping(item: TemplateItem) {
  error.value = ''
  notice.value = ''
  try {
    await platformRequest(`/api/system/templates/${item.id}`, {
      method: 'PUT',
      body: JSON.stringify({ fieldMapping: draftMapping.value }),
    })
    editingId.value = null
    notice.value = `模板“${item.name}”字段映射已保存。`
    await load()
  } catch (e) {
    error.value = normalizeError(e).message
  }
}

async function toggleActive(item: TemplateItem) {
  error.value = ''
  try {
    await platformRequest(`/api/system/templates/${item.id}`, {
      method: 'PUT',
      body: JSON.stringify({ isActive: !item.isActive }),
    })
    await load()
  } catch (e) {
    error.value = normalizeError(e).message
  }
}

async function removeItem(item: TemplateItem) {
  error.value = ''
  try {
    await platformRequest(`/api/system/templates/${item.id}`, { method: 'DELETE' })
    await load()
  } catch (e) {
    error.value = normalizeError(e).message
  }
}

async function downloadSampleExcel(kind: 'personnel' | 'equipment' | 'standards') {
  error.value = ''
  try {
    const token = getSessionToken()
    const resp = await fetch(`/api/system/sample-imports/${kind}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!resp.ok) throw new Error('下载模板失败')
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${kind}-import-template.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = normalizeError(e).message
  }
}

onMounted(() => { void load() })
</script>

<template>
  <div class="page-header d-print-none mb-3">
    <div class="row align-items-center">
      <div class="col">
        <div class="page-pretitle">系统管理</div>
        <h2 class="page-title">自定义模板与字段映射</h2>
      </div>
      <div class="col-auto d-flex flex-wrap gap-2">
        <button type="button" class="btn btn-outline-primary btn-sm" @click="downloadSampleExcel('personnel')">
          <i class="ti ti-download me-1" aria-hidden="true"></i>人员库示例 Excel
        </button>
        <button type="button" class="btn btn-outline-primary btn-sm" @click="downloadSampleExcel('equipment')">
          <i class="ti ti-download me-1" aria-hidden="true"></i>设备台账示例 Excel
        </button>
        <button type="button" class="btn btn-outline-primary btn-sm" @click="downloadSampleExcel('standards')">
          <i class="ti ti-download me-1" aria-hidden="true"></i>标准与CNAS资质示例 Excel
        </button>
      </div>
    </div>
  </div>

  <div v-if="error" class="alert alert-danger" role="alert">{{ error }}</div>
  <div v-if="notice" class="alert alert-success" role="status">{{ notice }}</div>

  <div class="card mb-3">
    <div class="card-header">
      <h3 class="card-title">上传自定义 Word 模板（.docx）</h3>
    </div>
    <form class="card-body" @submit.prevent="handleUpload">
      <div class="row g-3 align-items-end">
        <div class="col-md-3">
          <label for="tpl-kind" class="form-label">模板用途</label>
          <select id="tpl-kind" v-model="uploadKind" class="form-select">
            <option value="report">中文检测报告模板</option>
            <option value="commission">委托单模板</option>
          </select>
        </div>
        <div class="col-md-4">
          <label for="tpl-name" class="form-label">模板名称</label>
          <input id="tpl-name" v-model="uploadName" type="text" class="form-control" placeholder="例如：通用中文检测报告模板" />
        </div>
        <div class="col-md-3">
          <label for="tpl-file" class="form-label">选择 .docx 文件（支持 &#123;&#123;字段&#125;&#125; 占位符）</label>
          <input id="tpl-file" type="file" accept=".docx" class="form-control" @change="onFileChange" />
        </div>
        <div class="col-md-2">
          <button type="submit" class="btn btn-primary w-100" :disabled="uploading">
            <i class="ti ti-upload me-1" aria-hidden="true"></i>{{ uploading ? '上传中…' : '上传模板' }}
          </button>
        </div>
      </div>
    </form>
  </div>

  <div class="card">
    <div class="card-header">
      <h3 class="card-title">已上传模板列表</h3>
    </div>
    <div class="table-responsive">
      <table class="table table-vcenter card-table">
        <thead>
          <tr>
            <th>用途</th>
            <th>模板名称</th>
            <th>文件名</th>
            <th>识别占位符</th>
            <th>状态</th>
            <th class="text-end">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="6" class="text-center text-secondary py-4">正在加载模板列表…</td>
          </tr>
          <tr v-else-if="!items.length">
            <td colspan="6" class="text-center text-secondary py-4">暂未上传自定义模板，请在上方上传 .docx 文件后进行字段映射。</td>
          </tr>
          <template v-for="item in items" :key="item.id">
            <tr>
              <td>
                <span class="badge" :class="item.kind === 'report' ? 'bg-blue-lt text-blue' : 'bg-purple-lt text-purple'">
                  {{ item.kind === 'report' ? '中文报告' : '委托单' }}
                </span>
              </td>
              <td class="fw-medium">{{ item.name }}</td>
              <td class="text-secondary">{{ item.fileName }}</td>
              <td>
                <span v-if="!item.placeholders.length" class="text-secondary small">未检测到占位符</span>
                <span v-for="ph in item.placeholders" :key="ph" class="badge bg-secondary-lt me-1">{{ ph }}</span>
              </td>
              <td>
                <span class="badge" :class="item.isActive ? 'bg-success-lt text-success' : 'bg-secondary-lt text-secondary'">
                  {{ item.isActive ? '当前启用' : '未启用' }}
                </span>
              </td>
              <td class="text-end">
                <div class="btn-list justify-content-end flex-nowrap">
                  <button type="button" class="btn btn-sm btn-outline-primary" @click="startMapping(item)">字段映射</button>
                  <button type="button" class="btn btn-sm" :class="item.isActive ? 'btn-outline-warning' : 'btn-outline-success'" @click="toggleActive(item)">
                    {{ item.isActive ? '停用' : '设为默认' }}
                  </button>
                  <button type="button" class="btn btn-sm btn-outline-danger" @click="removeItem(item)">删除</button>
                </div>
              </td>
            </tr>
            <tr v-if="editingId === item.id">
              <td colspan="6" class="bg-body-tertiary">
                <div class="p-3">
                  <h4 class="mb-3">配置模板占位符与系统字段映射：{{ item.name }}</h4>
                  <div v-if="!item.placeholders.length" class="text-secondary">
                    该模板未包含 &#123;&#123;字段名&#125;&#125; 或 ${字段名} 占位符，可直接使用或重新上传带占位符的 .docx。
                  </div>
                  <div v-else class="row g-2">
                    <div v-for="ph in item.placeholders" :key="ph" class="col-md-4">
                      <label class="form-label small mb-1">模板占位符：<code>{{ ph }}</code></label>
                      <select v-model="draftMapping[ph]" class="form-select form-select-sm">
                        <option value="">-- 不映射 --</option>
                        <option v-for="sf in systemFields" :key="sf.key" :value="sf.key">{{ sf.label }} ({{ sf.key }})</option>
                      </select>
                    </div>
                  </div>
                  <div class="mt-3 d-flex gap-2">
                    <button type="button" class="btn btn-sm btn-primary" @click="saveMapping(item)">保存字段映射</button>
                    <button type="button" class="btn btn-sm btn-outline-secondary" @click="editingId = null">取消</button>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>
