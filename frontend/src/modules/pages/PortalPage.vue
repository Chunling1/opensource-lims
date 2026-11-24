<template>
  <ModuleWorkspace :title="pageName" :area-name="areaName" :module-name="moduleName" :path="route.path" :pages="pages" :active-key="pageKey" :show-command="false" :show-content="false">

  <section >
    <div>
      <span >EXTERNAL ENTRUSTMENT</span>
      <h2 class="h5 mb-3">外部网上委托受理工作台</h2>
      <p>统一查看外部客户提交的检测需求。受理后生成内部委托编号，驳回时请填写明确原因供客户修改。</p>
    </div>
    <div >
      <strong>{{ total }}</strong>
      <span>条申请</span>
    </div>
  </section>

  <ModuleCommandBar
    :count-label="`显示 ${rows.length} 条，共 ${total} 条`"
    show-search
    show-reset
    :search-loading="loading"
    @search="search"
    @reset="resetFilters"
  >
    <template #filters>
      <el-input
        v-model="keyword"
        clearable
        placeholder="搜索申请编号、客户、单位、方案名称或编号"
        @keyup.enter="search"
      />
      <el-select v-model="status" clearable placeholder="全部状态" @change="search">
        <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
    </template>
    <template #actions>
      <el-button :loading="loading" @click="load">刷新申请</el-button>
    </template>
  </ModuleCommandBar>

  <el-card shadow="never" >
    <template #header>
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
        <div>
          <strong>{{ pageKey === 'query' ? '网上委托申请查询' : '待办申请受理' }}</strong>
          <p>{{ pageKey === 'query' ? '查看全部外部申请及其受理结果' : '优先处理待受理和处理中的外部申请' }}</p>
        </div>
        <div class="d-flex flex-wrap gap-2">
          <el-tag v-for="item in statusOptions" :key="item.value" :type="item.type" effect="light">
            {{ item.label }}
          </el-tag>
        </div>
      </div>
    </template>

    <el-table v-loading="loading" :data="rows" border row-key="id" height="calc(100vh - 480px)">
      <el-table-column prop="applicationNo" label="申请编号" min-width="165" fixed="left">
        <template #default="{ row }">
          <button class="btn btn-light" type="button" @click="openDetail(row)">
            {{ row.applicationNo || `#${row.id}` }}
          </button>
        </template>
      </el-table-column>
      <el-table-column label="检测方案" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <div >{{ row.projectTitle || '未指定方案' }}</div>
          <div >{{ row.projectCode || '—' }}</div>
        </template>
      </el-table-column>
      <el-table-column label="客户信息" min-width="210" show-overflow-tooltip>
        <template #default="{ row }">
          <div >{{ row.companyName || row.customerName || '—' }}</div>
          <div >
            {{ [row.customerName, row.customerPhone].filter(Boolean).join(' · ') || '—' }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="预估金额" width="140" align="right">
        <template #default="{ row }">{{ amountText(row.estimatedAmount) }}</template>
      </el-table-column>
      <el-table-column label="提交时间" width="178">
        <template #default="{ row }">{{ dateTimeText(row.submittedAt) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="112" align="center">
        <template #default="{ row }">
          <el-tag :type="statusMeta(row.status).type" effect="light">
            {{ statusMeta(row.status).label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="internalEntrustNo" label="内部委托编号" min-width="150">
        <template #default="{ row }">{{ row.internalEntrustNo || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right" align="center">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">查看详情</el-button>
          <el-button v-if="canAccept(row)" link type="success" @click="accept(row)">受理</el-button>
          <el-button v-if="canReject(row)" link type="danger" @click="reject(row)">驳回</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无符合条件的外部委托申请" />
      </template>
    </el-table>

    <div >
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        background
        layout="sizes, prev, pager, next, total"
        :page-sizes="[10, 20, 50]"
        :total="total"
        @current-change="load"
        @size-change="handleSizeChange"
      />
    </div>
  </el-card>

  <el-dialog v-model="detailOpen" title="外部委托申请详情" width="min(920px, 94vw)" destroy-on-close @closed="resetCustomerServiceState">
    <template v-if="detailRow">
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
        <div>
          <span>申请编号</span>
          <strong>{{ detailRow.applicationNo || `#${detailRow.id}` }}</strong>
        </div>
        <el-tag :type="statusMeta(detailRow.status).type" effect="light" size="large">
          {{ statusMeta(detailRow.status).label }}
        </el-tag>
      </div>

      <el-descriptions :column="2" border >
        <el-descriptions-item label="客户单位">{{ detailRow.companyName || '—' }}</el-descriptions-item>
        <el-descriptions-item label="联系人">{{ detailRow.customerName || '—' }}</el-descriptions-item>
        <el-descriptions-item label="联系电话">{{ detailRow.customerPhone || '—' }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ dateTimeText(detailRow.submittedAt) }}</el-descriptions-item>
        <el-descriptions-item label="检测方案">
          {{ detailRow.projectTitle || '—' }}
          <span v-if="detailRow.projectCode" >{{ detailRow.projectCode }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="预估金额">{{ amountText(detailRow.estimatedAmount) }}</el-descriptions-item>
        <el-descriptions-item label="内部委托编号" :span="2">
          {{ detailRow.internalEntrustNo || '尚未生成' }}
        </el-descriptions-item>
        <el-descriptions-item v-if="detailRow.note" label="处理意见" :span="2">
          {{ detailRow.note }}
        </el-descriptions-item>
      </el-descriptions>

      <section >
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
          <strong>客户提交的委托信息</strong>
          <span>以下内容来自外部平台提交时的表单快照</span>
        </div>
        <el-descriptions v-if="formEntries.length" :column="2" border>
          <el-descriptions-item
            v-for="item in formEntries"
            :key="item.key"
            :label="item.label"
            :span="item.long ? 2 : 1"
          >
            <span >{{ item.value }}</span>
          </el-descriptions-item>
        </el-descriptions>
        <el-empty v-else description="客户未提交补充表单信息" :image-size="72" />
      </section>

      <section class="mb-3">
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
          <strong>客户交付与动态</strong>
          <span>向该客户发布证书/发票文件、维护物流或发送站内消息</span>
          <el-button link type="primary" :loading="customerServicesLoading" @click="loadCustomerServices">刷新</el-button>
        </div>
        <el-tabs v-model="customerServiceTab" >
          <el-tab-pane label="交付文件" name="documents">
            <div class="row g-3">
              <div class="list-group col-12 col-md-6" v-loading="customerServicesLoading">
                <div v-for="item in customerServices.documents" :key="item.id" class="d-flex flex-wrap align-items-center justify-content-between gap-2 py-2 border-bottom">
                  <div><strong>{{ item.title }}</strong><span>{{ item.kindLabel }} · {{ item.documentNo || item.fileName || '未填写编号' }}</span><small>{{ dateTimeText(item.publishedAt) }}</small></div>
                  <el-tag :type="item.status === 'available' ? 'success' : 'info'">{{ item.status === 'available' ? '已发布' : item.status }}</el-tag>
                  <el-button v-if="item.status === 'available' && canPublishDocumentKind(item.kind)" link type="danger" @click="withdrawDocument(item.id)">撤回</el-button>
                </div>
                <el-empty v-if="!customerServicesLoading && !customerServices.documents.length" description="尚未发布客户交付文件" :image-size="65" />
              </div>
              <el-form v-if="canPublishAnyCustomerDocument" label-position="top" class="col-12 col-md-6" @submit.prevent>
                <el-form-item label="文件类型"><el-select v-model="documentForm.kind"><el-option v-if="canPublishDocumentKind('certificate')" label="证书文件" value="certificate" /><el-option v-if="canPublishDocumentKind('invoice')" label="电子发票" value="invoice" /><el-option v-if="canPublishDocumentKind('other')" label="其他交付文件" value="other" /></el-select></el-form-item>
                <el-form-item label="客户可见标题"><el-input v-model="documentForm.title" maxlength="200" placeholder="例如：型式检验证书" /></el-form-item>
                <el-form-item label="文件/发票编号"><el-input v-model="documentForm.documentNo" maxlength="100" placeholder="选填" /></el-form-item>
                <el-form-item v-if="documentForm.kind === 'certificate'" label="关联报告编号"><el-input v-model="documentForm.reportNo" maxlength="40" placeholder="必须属于当前委托且已批准" /></el-form-item>
                <el-form-item label="签发日期"><FlatDatePicker v-model="documentForm.issuedAt" placeholder="选择签发日期" /></el-form-item>
                <el-form-item label="文件"><input ref="customerFileInput" class="form-control" type="file" accept=".pdf,.png,.jpg,.jpeg" @change="selectCustomerFile" /><small v-if="documentForm.file">{{ documentForm.file.name }}</small></el-form-item>
                <el-button type="primary" :loading="serviceSaving" :disabled="!canPublishDocumentKind(documentForm.kind)" @click="publishDocument">发布给客户</el-button>
              </el-form><el-alert v-else title="当前账号仅可查看客户交付信息" type="info" :closable="false" />
            </div>
          </el-tab-pane>
          <el-tab-pane label="快递物流" name="shipments">
            <div class="row g-3">
              <div class="list-group col-12 col-md-6" v-loading="customerServicesLoading">
                <div v-for="item in customerServices.shipments" :key="item.id" class="d-flex flex-wrap align-items-center justify-content-between gap-2 py-2 border-bottom">
                  <div><strong>{{ item.carrier }} · {{ item.trackingNo }}</strong><span>{{ item.latestEvent || '暂无最新轨迹描述' }}</span><small>{{ dateTimeText(item.updatedAt) }}</small></div>
                  <el-tag>{{ item.statusLabel }}</el-tag>
                  <el-button v-if="canManageCustomerServices" link type="primary" @click="editShipment(item)">更新</el-button>
                </div>
                <el-empty v-if="!customerServicesLoading && !customerServices.shipments.length" description="尚未建立物流记录" :image-size="65" />
              </div>
              <el-form v-if="canManageCustomerServices" label-position="top" class="col-12 col-md-6" @submit.prevent>
                <el-form-item label="承运公司"><el-input v-model="shipmentForm.carrier" maxlength="80" placeholder="例如：顺丰速运" /></el-form-item>
                <el-form-item label="快递单号"><el-input v-model="shipmentForm.trackingNo" maxlength="100" /></el-form-item>
                <el-form-item label="物流状态"><el-select v-model="shipmentForm.status"><el-option v-for="item in shipmentStatuses" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
                <el-form-item label="最新轨迹"><el-input v-model="shipmentForm.latestEvent" type="textarea" :rows="3" maxlength="300" show-word-limit /></el-form-item>
                <el-form-item label="寄出时间"><FlatDatePicker v-model="shipmentForm.shippedAt" mode="datetime" placeholder="选择寄出时间" /></el-form-item>
                <el-form-item v-if="shipmentForm.status === 'delivered'" label="签收时间"><FlatDatePicker v-model="shipmentForm.deliveredAt" mode="datetime" placeholder="留空则以当前时间记录" /></el-form-item>
                <el-button type="primary" :loading="serviceSaving" @click="saveShipment">{{ shipmentForm.id ? '更新物流' : '发布物流' }}</el-button>
                <el-button v-if="shipmentForm.id" @click="resetShipmentForm">取消编辑</el-button>
              </el-form><el-alert v-else title="当前账号仅可查看客户物流" type="info" :closable="false" />
            </div>
          </el-tab-pane>
          <el-tab-pane label="客户消息" name="notifications">
            <div class="row g-3">
              <div class="list-group col-12 col-md-6" v-loading="customerServicesLoading">
                <div v-for="item in customerServices.notifications" :key="item.id" class="d-flex flex-wrap align-items-center justify-content-between gap-2 py-2 border-bottom">
                  <div><strong>{{ item.title }}</strong><span>{{ item.content }}</span><small>{{ dateTimeText(item.publishedAt) }}</small></div>
                  <el-tag :type="item.read ? 'info' : 'warning'">{{ item.read ? '客户已读' : '未读' }}</el-tag>
                </div>
                <el-empty v-if="!customerServicesLoading && !customerServices.notifications.length" description="尚未向客户发送消息" :image-size="65" />
              </div>
              <el-form v-if="canManageCustomerServices" label-position="top" class="col-12 col-md-6" @submit.prevent>
                <el-form-item label="消息标题"><el-input v-model="notificationForm.title" maxlength="160" /></el-form-item>
                <el-form-item label="消息内容"><el-input v-model="notificationForm.content" type="textarea" :rows="5" maxlength="500" show-word-limit /></el-form-item>
                <el-button type="primary" :loading="serviceSaving" @click="publishNotification">发送站内消息</el-button>
              </el-form><el-alert v-else title="当前账号仅可查看客户消息" type="info" :closable="false" />
            </div>
          </el-tab-pane>
        </el-tabs>
      </section>
    </template>
    <template #footer>
      <el-button @click="detailOpen = false">关闭</el-button>
      <el-button v-if="detailRow && canReject(detailRow)" type="danger" plain @click="reject(detailRow)">
        驳回申请
      </el-button>
      <el-button v-if="detailRow && canAccept(detailRow)" type="primary" @click="accept(detailRow)">
        确认受理
      </el-button>
    </template>
  </el-dialog>
  </ModuleWorkspace>
</template>

<script setup lang="ts">
import { useLiveSearch, useSearchRequest } from '@/composables/liveSearch'
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'
import { modules } from '@/data/modules'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import ModuleCommandBar from '@/components/ModuleCommandBar.vue'
import FlatDatePicker from '@/components/FlatDatePicker.vue'
import { useSessionStore } from '@/stores/session'
import {
  acceptExternalEntrustment,
  getExternalCustomerServices,
  getExternalEntrustments,
  publishExternalCustomerDocument,
  publishExternalCustomerNotification,
  rejectExternalEntrustment,
  saveExternalCustomerShipment,
  withdrawExternalCustomerDocument,
  type ExternalCustomerServices,
  type ExternalEntrustment,
  type ExternalShipmentAdmin,
} from '@/services/publicPortalAdmin'

const route = useRoute()
const session = useSessionStore()
const moduleKey = computed(() => route.meta.moduleKey ?? '')
const pageKey = computed(() => String(route.meta.pageKey ?? 'application'))
const pageName = computed(() => String(route.meta.pageName ?? '网上委托办理'))
const areaName = computed(() => String(route.meta.areaName ?? '网上委托信息服务'))
const moduleName = computed(() => String(route.meta.moduleName ?? '网上委托'))
const pages = computed(() => modules.find((module) => module.key === moduleKey.value)?.pages ?? [])

const statusOptions = [
  { value: 'submitted', label: '待受理', type: 'warning' as const },
  { value: 'accepted', label: '已受理', type: 'success' as const },
  { value: 'rejected', label: '驳回', type: 'danger' as const },
  { value: 'cancelled', label: '客户已取消', type: 'info' as const },
]
const statusAliases: Record<string, string> = {
  submitted: 'submitted',
  pending: 'submitted',
  待受理: 'submitted',
  accepted: 'accepted',
  已受理: 'accepted',
  rejected: 'rejected',
  驳回: 'rejected',
  已驳回: 'rejected',
  cancelled: 'cancelled',
  已取消: 'cancelled',
}
const detailLabels: Record<string, string> = {
  entrustUnit: '委托单位',
  clientCompany: '委托单位',
  contactName: '委托人',
  contactPhone: '委托人电话',
  contactMobile: '委托人电话',
  projectName: '工程/项目名称',
  projectAddress: '工程地址',
  sampleName: '样品/工程名称',
  sampleModel: '规格型号',
  manufacturer: '生产厂家',
  sampleQuantity: '样品数量',
  sampleStatus: '样品状态',
  testItems: '检测项目',
  selectedTestItems: '客户选择的常见检测项目',
  testStandards: '检测依据',
  desiredDate: '期望完成日期',
  remarks: '备注',
}

const loading = ref(false)
const rows = ref<ExternalEntrustment[]>([])
const total = ref(0)
const keyword = ref('')
const status = ref('')
const page = ref(1)
const pageSize = ref(20)
const detailOpen = ref(false)
const detailRow = ref<ExternalEntrustment | null>(null)
const customerServicesLoading = ref(false)
const serviceSaving = ref(false)
const customerServiceTab = ref('documents')
const customerFileInput = ref<HTMLInputElement | null>(null)
let customerServicesRequest = 0
const customerServices = reactive<ExternalCustomerServices>({ documents: [], shipments: [], notifications: [] })
const documentForm = reactive<{ kind: 'certificate' | 'invoice' | 'other'; title: string; documentNo: string; reportNo: string; issuedAt: string; file: File | null }>({ kind: 'certificate', title: '', documentNo: '', reportNo: '', issuedAt: '', file: null })
const shipmentForm = reactive({
  id: undefined as number | undefined,
  carrier: '',
  trackingNo: '',
  status: 'shipped',
  latestEvent: '',
  shippedAt: '',
  deliveredAt: '',
  events: [] as ExternalShipmentAdmin['events'],
})
const notificationForm = reactive({ title: '', content: '' })
const shipmentStatuses = [
  { value: 'pending', label: '待寄出' }, { value: 'shipped', label: '已寄出' },
  { value: 'in_transit', label: '运输中' }, { value: 'delivering', label: '派送中' },
  { value: 'delivered', label: '已签收' }, { value: 'exception', label: '物流异常' },
]

const formEntries = computed(() => {
  const entries = Object.entries(detailRow.value?.formData ?? {})
  return entries
    .filter(([key, value]) => key !== 'selectedCapabilityHash' && value !== null && value !== undefined && value !== '')
    .map(([key, value]) => {
      const text = key === 'selectedTestItems' && Array.isArray(value)
        ? value.map((entry) => {
          if (!entry || typeof entry !== 'object') return ''
          const item = entry as { name?: string; standards?: Array<{ code?: string }> }
          const standards = (item.standards ?? []).map((standard) => standard.code).filter(Boolean).join('、')
          return `${item.name || '未命名项目'}${standards ? `（${standards}）` : ''}`
        }).filter(Boolean).join('；')
        : detailValue(value)
      return {
        key,
        label: detailLabels[key] ?? key,
        value: text,
        long: text.length > 60 || typeof value === 'object',
      }
    })
})
const canManageCustomerServices = computed(() => hasAction(
  'online_entrust.application.process',
  'online_entrust.process',
))
const canPublishAnyCustomerDocument = computed(() => (
  canPublishDocumentKind('certificate')
  || canPublishDocumentKind('invoice')
  || canPublishDocumentKind('other')
))

function canonicalStatus(value: string) {
  return statusAliases[String(value || '').trim()] ?? String(value || '').trim().toLowerCase()
}
function statusMeta(value: string) {
  const canonical = canonicalStatus(value)
  return statusOptions.find((item) => item.value === canonical)
    ?? { value: canonical, label: value || '未知', type: 'info' as const }
}
function hasAction(...codes: string[]) {
  if (session.businessReadOnly) return false
  return session.roleKey === 'admin' || session.account === 'admin' || codes.some((code) => session.canAction(code))
}
function canPublishDocumentKind(kind: string) {
  if (kind === 'certificate') return hasAction('report.print.pass')
  if (kind === 'invoice') return hasAction('finance.invoice.issue')
  return hasAction('online_entrust.application.process', 'online_entrust.process')
}
function canAccept(row: ExternalEntrustment) {
  return canonicalStatus(row.status) === 'submitted'
    && hasAction(
      'online_entrust.application.process',
      'online_entrust.application.accept',
      'online_entrust.accept',
    )
}
function canReject(row: ExternalEntrustment) {
  return canonicalStatus(row.status) === 'submitted'
    && hasAction(
      'online_entrust.application.process',
      'online_entrust.application.reject',
      'online_entrust.reject',
    )
}
function amountText(value: number | null) {
  if (value == null || !Number.isFinite(Number(value))) return '待确认'
  return `¥${Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
function dateTimeText(value: string) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}
function detailValue(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => detailValue(item)).join('、')
  if (value && typeof value === 'object') return JSON.stringify(value, null, 2)
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value)
}

const beginListSearch = useSearchRequest(() => [keyword.value, status.value, page.value, pageSize.value, pageKey.value])
async function load() {
  const current = beginListSearch()
  loading.value = true
  try {
    const result = await getExternalEntrustments({
      keyword: keyword.value.trim(),
      status: status.value,
      page: page.value,
      size: pageSize.value,
    })
    if (!current()) return
    rows.value = result.rows
    total.value = result.total
    if (detailRow.value) {
      detailRow.value = rows.value.find((item) => item.id === detailRow.value?.id) ?? detailRow.value
    }
  } catch (error) {
    if (!current()) return
    rows.value = []
    total.value = 0
    ElMessage.error(error instanceof Error ? error.message : '外部委托申请加载失败')
  } finally {
    if (current()) loading.value = false
  }
}
function search() {
  page.value = 1
  void load()
}
function resetFilters() {
  keyword.value = ''
  status.value = pageKey.value === 'application' ? 'submitted' : ''
  search()
}
function handleSizeChange() {
  page.value = 1
  void load()
}
function firstPublishableDocumentKind(): 'certificate' | 'invoice' | 'other' {
  if (canPublishDocumentKind('certificate')) return 'certificate'
  if (canPublishDocumentKind('invoice')) return 'invoice'
  return 'other'
}
function resetCustomerServiceState() {
  customerServicesRequest += 1
  customerServicesLoading.value = false
  serviceSaving.value = false
  customerServiceTab.value = 'documents'
  Object.assign(customerServices, { documents: [], shipments: [], notifications: [] })
  Object.assign(documentForm, {
    kind: firstPublishableDocumentKind(), title: '', documentNo: '', reportNo: '', issuedAt: '', file: null,
  })
  if (customerFileInput.value) customerFileInput.value.value = ''
  resetShipmentForm()
  Object.assign(notificationForm, { title: '', content: '' })
  detailRow.value = null
}
function openDetail(row: ExternalEntrustment) {
  resetCustomerServiceState()
  detailRow.value = row
  detailOpen.value = true
  void loadCustomerServices()
}

async function loadCustomerServices() {
  const applicationId = detailRow.value?.id
  if (!applicationId) return
  const requestId = ++customerServicesRequest
  customerServicesLoading.value = true
  try {
    const result = await getExternalCustomerServices(applicationId)
    if (requestId === customerServicesRequest && detailRow.value?.id === applicationId) {
      Object.assign(customerServices, result)
    }
  }
  catch (error) {
    if (requestId === customerServicesRequest && detailRow.value?.id === applicationId) {
      ElMessage.error(error instanceof Error ? error.message : '客户交付信息加载失败')
    }
  }
  finally {
    if (requestId === customerServicesRequest) customerServicesLoading.value = false
  }
}
function selectCustomerFile(event: Event) {
  documentForm.file = (event.target as HTMLInputElement).files?.[0] ?? null
}
async function publishDocument() {
  if (!detailRow.value || !canPublishDocumentKind(documentForm.kind) || !documentForm.title.trim() || !documentForm.file) {
    ElMessage.warning('请填写客户可见标题并选择文件')
    return
  }
  if (documentForm.kind === 'certificate' && (!documentForm.documentNo.trim() || !documentForm.reportNo.trim())) {
    ElMessage.warning('发布证书必须填写证书编号和关联报告编号')
    return
  }
  serviceSaving.value = true
  try {
    await publishExternalCustomerDocument(detailRow.value.id, {
      kind: documentForm.kind, title: documentForm.title.trim(), documentNo: documentForm.documentNo.trim(),
      reportNo: documentForm.reportNo.trim(), issuedAt: documentForm.issuedAt, file: documentForm.file,
    })
    Object.assign(documentForm, { kind: firstPublishableDocumentKind(), title: '', documentNo: '', reportNo: '', issuedAt: '', file: null })
    if (customerFileInput.value) customerFileInput.value.value = ''
    ElMessage.success('文件已发布到客户工作台')
    await loadCustomerServices()
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '文件发布失败') }
  finally { serviceSaving.value = false }
}
async function withdrawDocument(documentId: string | number) {
  if (!detailRow.value) return
  try {
    await ElMessageBox.confirm('撤回后客户将不能继续下载该文件，历史文件本体仍按审计规则保留。', '撤回客户文件', { type: 'warning' })
    await withdrawExternalCustomerDocument(detailRow.value.id, documentId)
    ElMessage.success('客户文件已撤回')
    await loadCustomerServices()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error instanceof Error ? error.message : '撤回失败')
  }
}
function editShipment(item: ExternalShipmentAdmin) {
  Object.assign(shipmentForm, {
    id: item.id,
    carrier: item.carrier,
    trackingNo: item.trackingNo,
    status: item.status,
    latestEvent: item.latestEvent,
    shippedAt: item.shippedAt,
    deliveredAt: item.deliveredAt,
    events: item.events.map((event) => ({ ...event })),
  })
}
function resetShipmentForm() {
  Object.assign(shipmentForm, {
    id: undefined, carrier: '', trackingNo: '', status: 'shipped', latestEvent: '', shippedAt: '', deliveredAt: '', events: [],
  })
}
async function saveShipment() {
  if (!detailRow.value || !shipmentForm.carrier.trim() || !shipmentForm.trackingNo.trim()) {
    ElMessage.warning('请填写承运公司和快递单号')
    return
  }
  serviceSaving.value = true
  try {
    await saveExternalCustomerShipment(detailRow.value.id, { ...shipmentForm })
    ElMessage.success('物流状态已发布给客户')
    resetShipmentForm()
    await loadCustomerServices()
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '物流更新失败') }
  finally { serviceSaving.value = false }
}
async function publishNotification() {
  if (!detailRow.value || !notificationForm.title.trim() || !notificationForm.content.trim()) {
    ElMessage.warning('请填写消息标题和内容')
    return
  }
  serviceSaving.value = true
  try {
    await publishExternalCustomerNotification(detailRow.value.id, { title: notificationForm.title.trim(), content: notificationForm.content.trim() })
    Object.assign(notificationForm, { title: '', content: '' })
    ElMessage.success('站内消息已发送')
    await loadCustomerServices()
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '消息发送失败') }
  finally { serviceSaving.value = false }
}
async function accept(row: ExternalEntrustment) {
  try {
    const { value } = await ElMessageBox.prompt(
      `确认受理外部申请「${row.applicationNo || row.id}」？可填写内部受理备注。`,
      '受理网上委托',
      {
        confirmButtonText: '确认受理',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputPlaceholder: '选填：内部处理说明或交接信息',
      },
    )
    await acceptExternalEntrustment(row.id, String(value ?? '').trim())
    ElMessage.success('申请已受理，并已进入内部委托流程')
    await load()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error instanceof Error ? error.message : '受理失败')
    }
  }
}
async function reject(row: ExternalEntrustment) {
  try {
    const { value } = await ElMessageBox.prompt(
      `请填写驳回申请「${row.applicationNo || row.id}」的原因，客户将据此修改或补充材料。`,
      '驳回网上委托',
      {
        confirmButtonText: '确认驳回',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputPlaceholder: '必填：说明缺失资料、不受理原因或修改要求',
        inputValidator: (input) => String(input ?? '').trim().length > 0 || '请填写驳回原因',
      },
    )
    await rejectExternalEntrustment(row.id, String(value ?? '').trim())
    ElMessage.success('申请已驳回，处理意见已保存')
    await load()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error instanceof Error ? error.message : '驳回失败')
    }
  }
}

watch(pageKey, (key) => {
  keyword.value = ''
  status.value = key === 'application' ? 'submitted' : ''
  page.value = 1
  void load()
}, { immediate: true })
useLiveSearch(keyword, search)
</script>


