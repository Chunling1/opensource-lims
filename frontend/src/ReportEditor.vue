<script setup lang="ts">
import ReasonModal from './ReasonModal.vue'
import DateInput from './DateInput.vue'
import { ref } from 'vue'
import { IconFileTypePdf, IconCircleCheck, IconUpload, IconSend } from '@tabler/icons-vue'
import { reportStates, type Command, type Sample, type Report } from './api'
const props = defineProps<{
  sample: Sample
  report: Report
  pending: boolean
  error: string
  act: Command
}>()
const kind = ref('source'),
  replaces = ref(''),
  start = ref(props.report.start ?? ''),
  end = ref(props.report.end ?? '')
const site = ref(props.sample.siteDate ?? ''),
  reviewer = ref(''),
  file = ref<File>(),
  input = ref<HTMLInputElement>()
const cancelOpen = ref(false)
const emit = defineEmits<{ 'open-modal': [] }>()
function openCancel() {
  emit('open-modal')
  cancelOpen.value = true
}
async function cancel(reason: string) {
  if (await props.act('cancel', { reportId: props.report.id, reason })) cancelOpen.value = false
}
async function upload() {
  if (!file.value) return
  if (
    await props.act('upload', {
      reportId: props.report.id,
      kind: kind.value,
      file: file.value,
      ...(replaces.value && kind.value === 'source' ? { replaces: Number(replaces.value) } : {}),
    })
  ) {
    file.value = undefined
    replaces.value = ''
    if (input.value) input.value.value = ''
  }
}
function selectFile(e: Event) {
  file.value = (e.target as HTMLInputElement).files?.[0]
}
</script>
<template>
  <article class="card-body border-bottom">
    <div class="d-flex flex-wrap align-items-center gap-3 mb-3">
      <h3 class="mb-0">{{ report.number }}</h3>
      <span
        class="status"
        :class="
          report.state === 'review'
            ? 'status-teal'
            : report.state === 'draft'
              ? 'status-blue'
              : 'status-secondary'
        "
        ><span class="status-dot"></span>{{ reportStates[report.state] }}</span
      >
    </div>
    <div v-if="report.state === 'review'" class="alert alert-success" role="note">
      <div class="alert-icon"><IconCircleCheck class="icon" /></div>
      <div>
        <h4 class="alert-heading">{{ sample.designated ? '已交指定审核人' : '已进入审核待办池' }}</h4>
        <div class="alert-description">检测日期 {{ report.start }} 至 {{ report.end }}</div>
      </div>
    </div>
    <ol
      v-if="report.state !== 'cancelled'"
      class="steps steps-counter border-0 ms-0 ps-0 my-4"
      aria-label="报告编制进度"
    >
      <li
        v-for="(item, i) in ['上传原始记录', '上传待签报告', '送审']"
        :key="item"
        class="step-item"
        :class="{
          active:
            i ===
            (report.state === 'review'
              ? 2
              : !report.files.some((f) => f.kind === 'source')
                ? 0
                : !report.files.some((f) => f.kind === 'draft')
                  ? 1
                  : 2),
        }"
      >
        <span
          v-if="
            i === 2
              ? report.state === 'review'
              : report.files.some((f) => f.kind === (i === 0 ? 'source' : 'draft'))
          "
          class="text-success"
          aria-label="已完成"
          >✓ </span
        >{{ item }}
      </li>
    </ol>
    <div v-if="report.files.length" class="card card-sm mb-3">
     <div class="card-header"><h4 class="card-title">已上传资料</h4></div>
     <div class="table-responsive">
      <table class="table table-vcenter card-table">
        <thead>
          <tr>
            <th>报告文件</th>
            <th>类型</th>
            <th class="d-none d-md-table-cell">上传人 / 时间</th>
            <th class="d-none d-md-table-cell">大小 / SHA-256</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in report.files" :key="f.id">
            <td>
              <span class="avatar avatar-sm bg-red-lt me-2 d-none d-md-inline-flex"
                ><IconFileTypePdf class="icon" /></span
              ><a :href="'/api/files/' + f.id">{{ f.name }}</a>
            </td>
            <td>{{ f.kind === 'source' ? '原始记录' : '待签报告' }}</td>
            <td class="d-none d-md-table-cell">
              {{ f.uploader }}
              <div class="small text-secondary">{{ f.created.replace('T', ' ').slice(0, 19) }}</div>
            </td>
            <td class="d-none d-md-table-cell">
              {{ f.size < 1024 ? f.size + ' B' : (f.size / 1024).toFixed(1) + ' KB' }}
              <div class="small text-secondary">{{ f.sha256.slice(0, 8) }}</div>
            </td>
          </tr>
        </tbody>
      </table>
     </div>
    </div>
    <div v-if="report.state === 'draft'" class="row row-cards">
      <div v-if="'upload' in report.actions" class="col-lg-6">
        <form class="card card-sm h-100" @submit.prevent="upload">
          <div class="card-header">
            <h4 class="card-title"><IconUpload class="icon me-2" />上传资料</h4>
          </div>
          <div class="card-body">
            <div class="row g-3">
              <div class="col-sm-6">
                <label class="form-label" for="up-kind">资料类型</label
                ><select id="up-kind" v-model="kind" class="form-select" @change="replaces = ''">
                  <option value="source">原始记录</option>
                  <option value="draft">待签报告</option>
                </select>
              </div>
              <div v-if="kind === 'source'" class="col-sm-6">
                <label class="form-label" for="up-mode">保存方式</label
                ><select id="up-mode" v-model="replaces" class="form-select">
                  <option value="">新增原始记录</option>
                  <option
                    v-for="f in report.files.filter((f) => f.kind === 'source')"
                    :key="f.id"
                    :value="String(f.id)"
                  >
                    替换 {{ f.name }}
                  </option>
                </select>
              </div>
              <div class="col-12">
                <label class="form-label required" for="up-file">PDF 文件</label
                ><input
                  id="up-file"
                  ref="input"
                  class="form-control"
                  type="file"
                  accept="application/pdf,.pdf"
                  required
                  @change="selectFile"
                />
                <small class="form-hint">仅接受 PDF；文件内容与扩展名均须为 PDF。</small>
              </div>
            </div>
          </div>
          <div class="card-footer">
            <span class="d-inline-block" :title="report.actions.upload"
              ><button
                class="btn btn-primary"
                :title="report.actions.upload"
                :disabled="pending || !!report.actions.upload"
              >
                <span v-if="pending" class="spinner-border spinner-border-sm me-1"></span
                >{{ pending ? '处理中…' : '保存 PDF' }}
              </button></span
            ><small class="d-block text-secondary">{{ report.actions.upload }}</small>
          </div>
        </form>
      </div>
      <div v-if="'submit' in report.actions" class="col-lg-6">
        <form
          class="card card-sm h-100"
          @submit.prevent="
            act('submit', {
              reportId: report.id,
              start,
              end,
              ...(sample.physical ? {} : { siteDate: site }),
              ...(sample.designated ? { reviewerId: Number(reviewer) } : {}),
            })
          "
        >
          <div class="card-header">
            <h4 class="card-title"><IconSend class="icon me-2" />送审信息</h4>
          </div>
          <div class="card-body">
            <div class="row g-3">
              <div class="col-sm-6">
                <label class="form-label required" for="d-start">检测开始日期</label>
                <DateInput
                  id="d-start"
                  v-model="start"
                  :min="sample.receivedDate ?? undefined"
                  :max="end || sample.today"
                  required
                /><small v-if="!start" class="form-hint">尚未选择日期</small>
              </div>
              <div class="col-sm-6">
                <label class="form-label required" for="d-end">检测结束日期</label>
                <DateInput
                  id="d-end"
                  v-model="end"
                  :min="start || sample.receivedDate || undefined"
                  :max="sample.today"
                  required
                /><small v-if="!end" class="form-hint">尚未选择日期</small>
              </div>
              <div v-if="!sample.physical" class="col-sm-6">
                <label class="form-label required" for="d-site">现场检测日期</label>
                <DateInput id="d-site" v-model="site" :min="sample.commissionDate" :max="sample.today" required />
                <small v-if="!site" class="form-hint">尚未选择日期</small>
              </div>
              <div v-if="sample.designated" class="col-sm-6">
                <label class="form-label required" for="d-reviewer">下一办理人</label
                ><select id="d-reviewer" v-model="reviewer" class="form-select" required>
                  <option value="">请选择审核人</option>
                  <option v-for="u in report.reviewers" :key="u.id" :value="String(u.id)">
                    {{ u.name }}
                  </option>
                </select>
              </div>
            </div>
            <div v-if="report.actions.submit" class="alert alert-warning mt-3 mb-0">
              {{ report.actions.submit }}
            </div>
          </div>
          <div class="card-footer">
            <span class="d-inline-block" :title="report.actions.submit"
              ><button
                class="btn btn-primary"
                :title="report.actions.submit"
                :disabled="pending || !!report.actions.submit"
              >
                <span v-if="pending" class="spinner-border spinner-border-sm me-1"></span
                >{{ pending ? '处理中…' : '提交审核' }}
              </button></span
            >
          </div>
        </form>
      </div>
      <div v-if="'cancel' in report.actions" class="col-12">
        <div class="d-flex flex-wrap align-items-center gap-2 border-top pt-3">
          <span class="d-inline-block" :title="report.actions.cancel"
            ><button
              class="btn btn-outline-danger btn-sm"
              :title="report.actions.cancel"
              :disabled="pending || !!report.actions.cancel"
              @click="openCancel"
            >
              取消草稿
            </button></span
          ><small class="d-block text-secondary">{{ report.actions.cancel }}</small>
        </div>
        <ReasonModal
          v-if="cancelOpen"
          :title="'取消 ' + report.number"
          reason-label="取消原因"
          :pending="pending"
          :error="error"
          @close="cancelOpen = false"
          @confirm="cancel"
        />
      </div>
    </div>
  </article>
</template>
