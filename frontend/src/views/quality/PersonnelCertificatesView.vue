<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import PageHeading from '../../components/common/PageHeading.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import AttachmentFileList from '../../components/common/AttachmentFileList.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import LoadState from '../../components/common/LoadState.vue'
import CertificateListPanel from '../../components/quality/CertificateListPanel.vue'
import CertificateFormModal from '../../components/quality/CertificateFormModal.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import type { DemoAttachment } from '../../types/commissions/registration'
import type { CertificateListRow, CertificateOptions, CertificateDetail, ApprovedProjectDetail } from '../../types/quality/certificates'
import { downloadBlob } from '../../services/reports/reportPdf'
import type { TableColumn } from '../../types/common/table'
const peopleColumns: TableColumn[] = [
  { key: 'code', label: '编号', required: true }, { key: 'name', label: '姓名', default: true },
  { key: 'gender', label: '性别', default: true }, { key: 'department', label: '所在部门', default: true }, { key: 'position', label: '职务', default: true },
]
const certificateColumns: TableColumn[] = [
  { key: 'code', label: '编号', default: true }, { key: 'name', label: '姓名', default: true },
  { key: 'category', label: '上岗证类别', default: true }, { key: 'number', label: '上岗证号', required: true },
  { key: 'notes', label: '备注', truncate: 30, fullTitle: true }, { key: 'attachments', label: '附件' },
]

const peopleCache = ref<Record<string, CertificateListRow>>({}), certificateCache = ref<Record<string, CertificateListRow>>({}), projectCache = ref<Record<string, CertificateListRow>>({})
function remember(cache: Record<string, CertificateListRow>, rows: CertificateListRow[]) { rows.forEach(row => { cache[row.id] = row }) }
const options = ref<CertificateOptions>({ departments: [], categories: [], projectCategories: [] })
const optionsError = ref<ErrorValue>(''), peopleLoading = ref(false), certificatesLoading = ref(false)
const canWrite = computed(() => currentActor.value.roles.some(r => ['admin', 'quality'].includes(r)))
let alive = true, optionsController: AbortController | undefined, detailController: AbortController | undefined, filesController: AbortController | undefined
async function loadOptions() {
  optionsController?.abort(); const active = optionsController = new AbortController(); optionsError.value = ''
  try { const data = await registrationDemo.certificateOptions(active.signal); if (alive && !active.signal.aborted) options.value = data }
  catch (issue) { if (alive && !active.signal.aborted) optionsError.value = normalizeError(issue) }
}
const peopleFields = computed(() => [{ key: 'code', label: '编号' }, { key: 'name', label: '姓名' }, { key: 'department', label: '所在部门', options: options.value.departments }, { key: 'position', label: '职务' }])
const certificateFields = computed(() => [{ key: 'category', label: '上岗证类别', options: options.value.categories }, { key: 'number', label: '上岗证号' }, { key: 'name', label: '姓名' }])
const projectFields = [{ key: 'code', label: '项目代码' }, { key: 'item', label: '检测项目' }]
const selectedPeople = ref<string[]>([]), selectedCertificates = ref<string[]>([]), selectedProjects = ref<string[]>([])
const certificateScope = ref<'related' | 'all'>('related'), projectScope = ref<'related' | 'all'>('related')
const certificateReset = ref(0), projectReset = ref(0)
const showOwners = computed(() => projectScope.value === 'all' || selectedCertificates.value.length > 1)
const projectColumns = computed<TableColumn[]>(() => [
  { key: 'code', label: '检测项目代码', required: true }, { key: 'item', label: '核准检测项目', default: true }, { key: 'category', label: '类别', default: true },
  ...(showOwners.value ? [{ key: 'name', label: '姓名', required: true }, { key: 'number', label: '上岗证号', required: true }] : []),
  { key: 'notes', label: '备注', truncate: 30, fullTitle: true },
])

const peopleCaption = computed(() => {
  const person = peopleCache.value[selectedPeople.value[0] || '']
  return selectedPeople.value.length === 1 && person ? `${person.name} · ${person.code}` : selectedPeople.value.length ? `已选 ${selectedPeople.value.length} 人` : '未选择人员'
})
const certificateCaption = computed(() => selectedCertificates.value.length === 1 ? certificateCache.value[selectedCertificates.value[0] || '']?.number : undefined)
function selectCertificates(ids: string[]) { selectedCertificates.value = ids; selectedProjects.value = []; projectReset.value++ }
function selectPeople(ids: string[]) { selectedPeople.value = ids; selectCertificates([]); certificateReset.value++ }
function changeCertificateScope(scope: 'related' | 'all') { if (certificateScope.value === scope) return; certificateScope.value = scope; selectCertificates([]); certificateReset.value++ }
function changeProjectScope(scope: 'related' | 'all') { if (projectScope.value === scope) return; projectScope.value = scope; selectedProjects.value = []; projectReset.value++ }
const message = ref(''), messageTone = ref<'success' | 'warning'>('warning')
async function notify(text: string, tone: 'success' | 'warning') { message.value = ''; messageTone.value = tone; await nextTick(); if (alive) message.value = text }
type Editor = { kind: 'certificate' | 'project'; mode: 'new' | 'edit'; ownerId: string; ownerIds?: string[]; owner: string; record?: CertificateListRow }
const editor = ref<Editor>()
const editorCategories = computed(() => editor.value?.kind === 'project' ? options.value.projectCategories : options.value.categories)
function openCertificate(id?: string) {
  if (!canWrite.value) return
  const record = id ? certificateCache.value[id] : undefined, person = peopleCache.value[selectedPeople.value[0] || '']
  if (!record && (!person || selectedPeople.value.length !== 1)) return
  editor.value = { kind: 'certificate', mode: record ? 'edit' : 'new', ownerId: record?.personId || person!.id, owner: `${record?.name || person!.name} · ${record?.code || person!.code}`, record }
}
function addProjects() {
  if (!canWrite.value) return
  const targets = selectedCertificates.value.map(id => certificateCache.value[id]).filter((row): row is CertificateListRow => !!row)
  if (!targets.length || targets.length !== selectedCertificates.value.length) return
  editor.value = { kind: 'project', mode: 'new', ownerId: targets[0]!.id, ownerIds: targets.map(c => c.id), owner: `${targets.length > 1 ? `已选 ${targets.length} 张：` : ''}${targets.map(c => `${c.name} · ${c.number}`).join('；')}` }
}
function openProject(certificateId: string, id: string) {
  const record = projectCache.value[id]
  if (!canWrite.value || !record) return
  editor.value = { kind: 'project', mode: 'edit', ownerId: certificateId, owner: `${record.name} · ${record.number}`, record }
}
function saved(count: number) {
  const current = editor.value; editor.value = undefined
  certificateReset.value++; projectReset.value++; void loadOptions()
  void notify(current?.kind === 'project' && current.mode === 'new' ? `已为 ${count} 张上岗证新增项目。` : '保存成功。', 'success')
}
const deleting = ref<{ kind: 'certificate' | 'project'; id: string }>(), deletionTarget = ref<CertificateDetail | ApprovedProjectDetail>()
const deletingBusy = ref(false), deletionLoading = ref(false), deletionError = ref<ErrorValue>('')
const deletionDisplay = computed(() => deletionTarget.value || (deleting.value?.kind === 'certificate' ? certificateCache.value : projectCache.value)[deleting.value?.id || ''])
const deletionImpact = computed(() => {
  const row = deletionTarget.value
  if (!row || !('files' in row)) return ''
  const parts = [row.projectCount ? `${row.projectCount} 个核准项目` : '', row.files.length ? `${row.files.length} 个附件` : ''].filter(Boolean)
  return parts.length ? `同时删除该上岗证下的 ${parts.join('和 ')}。` : ''
})
async function openDelete(kind: 'certificate' | 'project', id: string, refresh = false) {
  if (!canWrite.value || deletingBusy.value) return
  detailController?.abort(); const active = detailController = new AbortController()
  if (deleting.value?.id !== id || deleting.value.kind !== kind) deletionTarget.value = undefined
  deleting.value = { kind, id }; deletionError.value = ''
  const cached = projectCache.value[id]
  if (kind === 'project' && !refresh && cached) {
    deletionTarget.value = { id, certificateId: cached.certificateId!, version: Number(cached.version), code: cached.code!, item: cached.item!, category: cached.category!, notes: cached.notes!, name: cached.name!, number: cached.number! }
    deletionLoading.value = false
    return
  }
  deletionLoading.value = true
  try {
    const row = kind === 'certificate' ? await registrationDemo.certificateDetail(id, active.signal) : await registrationDemo.approvedProjectDetail(id, active.signal)
    if (alive && !active.signal.aborted) deletionTarget.value = row
  } catch (issue) { if (alive && !active.signal.aborted) deletionError.value = normalizeError(issue) }
  finally { if (alive && !active.signal.aborted) deletionLoading.value = false }
}
function closeDelete() { if (deletingBusy.value) return; detailController?.abort(); deleting.value = undefined }
async function confirmDelete() {
  const target = deleting.value, row = deletionTarget.value
  const actorId = currentActor.value.id
  if (!target || !row || deletingBusy.value || deletionLoading.value || deletionError.value) return
  deletingBusy.value = true; deletionError.value = ''
  try {
    await registrationDemo.deleteCertificateRecord(target.kind === 'certificate' ? 'certificates' : 'projects', target.id, { version: row.version, ...('projectCount' in row ? { projectCount: row.projectCount } : {}) })
    if (!alive || actorId !== currentActor.value.id) return
    if (target.kind === 'certificate' && selectedCertificates.value.includes(target.id)) selectCertificates(selectedCertificates.value.filter(id => id !== target.id))
    else selectedProjects.value = selectedProjects.value.filter(id => id !== target.id)
    certificateReset.value++; projectReset.value++; deleting.value = undefined; void loadOptions()
    void notify('删除成功。', 'success')
  } catch (issue) { if (alive && actorId === currentActor.value.id) deletionError.value = normalizeError(issue) }
  finally { if (alive) deletingBusy.value = false }
}
const attachmentCertificate = ref<string>(), attachmentTitle = ref(''), attachmentFiles = ref<DemoAttachment[]>([])
const filesLoading = ref(false), fileBusy = ref(false), filesError = ref<ErrorValue>('')
async function openFiles(id: string) {
  filesController?.abort(); const active = filesController = new AbortController()
  attachmentCertificate.value = id; attachmentTitle.value = certificateCache.value[id]?.number || ''; attachmentFiles.value = []; filesError.value = ''; filesLoading.value = true
  try { const row = await registrationDemo.certificateDetail(id, active.signal); if (alive && !active.signal.aborted) { attachmentTitle.value = row.number; attachmentFiles.value = row.files } }
  catch (issue) { if (alive && !active.signal.aborted) filesError.value = normalizeError(issue) }
  finally { if (alive && !active.signal.aborted) filesLoading.value = false }
}
function closeFiles() { filesController?.abort(); attachmentCertificate.value = undefined }
async function downloadAttachment(file: DemoAttachment) {
  const id = attachmentCertificate.value
  if (!id || fileBusy.value) return
  fileBusy.value = true; filesError.value = ''
  try { const blob = await registrationDemo.certificateFile(id, file.id); if (alive && attachmentCertificate.value === id) downloadBlob(blob, file.name) }
  catch (issue) { if (alive && attachmentCertificate.value === id) filesError.value = normalizeError(issue) }
  finally { if (alive) fileBusy.value = false }
}
watch(() => currentActor.value.id, () => {
  editor.value = undefined; deleting.value = undefined; attachmentCertificate.value = undefined
  detailController?.abort(); filesController?.abort()
  peopleCache.value = {}; certificateCache.value = {}; projectCache.value = {}
  selectPeople([]); message.value = ''; options.value = { departments: [], categories: [], projectCategories: [] }; void loadOptions()
}, { immediate: true })
onBeforeUnmount(() => { alive = false; optionsController?.abort(); detailController?.abort(); filesController?.abort() })
</script>

<template>
  <PageHeading title="上岗证信息" />
  <ErrorNotice :error="optionsError" retry @retry="loadOptions" />
  <CertificateListPanel label="人员" kind="people" @loaded="remember(peopleCache, $event)" @loading="peopleLoading = $event" :columns="peopleColumns" :fields="peopleFields" :selected="selectedPeople" collapsible row-filters-children :selection-caption="peopleCaption" @update:selected="selectPeople" />
  <div class="row">
    <div class="col-12">
      <CertificateListPanel label="上岗证" kind="certificates" :scope="certificateScope" :parent-ids="selectedPeople" @loaded="remember(certificateCache, $event)" @loading="certificatesLoading = $event" :columns="certificateColumns" :fields="certificateFields" :selected="selectedCertificates" row-filters-children :relation-key="String(certificateReset)" :selection-caption="certificateCaption" :active-scope-tab="`certificates-${certificateScope}-tab`" :empty-prompt="certificateScope === 'related' && !selectedPeople.length ? '请选择人员' : undefined" @update:selected="selectCertificates">
        <template #header-actions><button type="button" class="btn btn-primary text-nowrap" :disabled="!canWrite || peopleLoading || selectedPeople.length !== 1" :title="selectedPeople.length !== 1 ? '请选择一名人员' : undefined" @click="openCertificate()"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增上岗证</button></template>
        <template #scope>
          <div class="nav nav-tabs nav-tabs-custom border-bottom-0" role="tablist" aria-label="上岗证查询范围">
            <button id="certificates-related-tab" type="button" class="nav-link" :class="{ active: certificateScope === 'related' }" role="tab" :aria-selected="certificateScope === 'related'" aria-controls="上岗证-panel" @click="changeCertificateScope('related')">当前人员</button>
            <button id="certificates-all-tab" type="button" class="nav-link" :class="{ active: certificateScope === 'all' }" role="tab" :aria-selected="certificateScope === 'all'" aria-controls="上岗证-panel" @click="changeCertificateScope('all')">全部上岗证</button>
          </div>
          <span v-if="certificateScope === 'related' && selectedPeople.length" class="text-muted small text-break py-2">{{ peopleCaption }}</span>
        </template>
        <template #attachments="{ row }"><button type="button" class="btn btn-link p-0 text-nowrap" :aria-label="`查看附件 ${row.number}`" @click="openFiles(row.id)"><i class="ti ti-paperclip me-1" aria-hidden="true"></i>{{ row.attachments }} 个附件</button></template>
        <template #actions="{ row }">
          <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="openCertificate(row.id)"><i class="ti ti-edit me-2" aria-hidden="true"></i>编辑</button>
          <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="openDelete('certificate', row.id)"><i class="ti ti-trash me-2" aria-hidden="true"></i>删除</button>
        </template>
      </CertificateListPanel>
    </div>
    <div class="col-12">
      <CertificateListPanel label="核准项目" kind="projects" :scope="projectScope" :parent-ids="selectedCertificates" @loaded="remember(projectCache, $event)" :columns="projectColumns" :fields="projectFields" :selected="selectedProjects" :relation-key="String(projectReset)" :active-scope-tab="`projects-${projectScope}-tab`" :empty-prompt="projectScope === 'related' && !selectedCertificates.length ? '请选择上岗证' : undefined" @update:selected="selectedProjects = $event">
        <template #header-actions><button type="button" class="btn btn-primary text-nowrap" :disabled="!canWrite || certificatesLoading || !selectedCertificates.length" :title="!selectedCertificates.length ? '请至少选择一张上岗证' : undefined" @click="addProjects"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增项目</button></template>
        <template #scope>
          <div class="nav nav-tabs nav-tabs-custom border-bottom-0" role="tablist" aria-label="核准项目查询范围">
            <button id="projects-related-tab" type="button" class="nav-link" :class="{ active: projectScope === 'related' }" role="tab" :aria-selected="projectScope === 'related'" aria-controls="核准项目-panel" @click="changeProjectScope('related')">当前上岗证</button>
            <button id="projects-all-tab" type="button" class="nav-link" :class="{ active: projectScope === 'all' }" role="tab" :aria-selected="projectScope === 'all'" aria-controls="核准项目-panel" @click="changeProjectScope('all')">全部核准项目</button>
          </div>
          <span v-if="projectScope === 'related' && selectedCertificates.length" class="text-muted small text-break py-2">{{ certificateCaption || `已选 ${selectedCertificates.length} 张上岗证` }}</span>
        </template>
        <template #actions="{ row }">
          <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="openProject(row.certificateId, row.id)"><i class="ti ti-edit me-2" aria-hidden="true"></i>编辑</button>
          <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="openDelete('project', row.id)"><i class="ti ti-trash me-2" aria-hidden="true"></i>删除</button>
        </template>
      </CertificateListPanel>
    </div>
  </div>
  <BootstrapModal :loading="filesLoading" :open="!!attachmentCertificate" :title="`上岗证附件 · ${attachmentTitle}`" size="lg" compact-height @close="closeFiles">
    <LoadState v-if="filesLoading" loading />
    <ErrorNotice v-else-if="filesError" :error="filesError" retry @retry="openFiles(attachmentCertificate!)" />
    <AttachmentFileList v-else :files="attachmentFiles" :can-attach="false" :busy="fileBusy" fill-empty @download="downloadAttachment" />
    <template #footer><button type="button" class="btn btn-light" @click="closeFiles">关闭</button></template>
  </BootstrapModal>
  <BootstrapModal v-if="deleting" open :title="deleting.kind === 'certificate' ? '删除上岗证' : '删除核准检测项目'" scrollable body-class="py-2" :busy="deletingBusy" @close="closeDelete">
    <template v-if="deletionDisplay && deleting.kind === 'certificate'">
      <p class="text-break">确认删除 {{ deletionDisplay.name }} 的上岗证“{{ deletionDisplay.number }}”？</p>
      <p v-if="!deletionLoading && deletionImpact" class="text-muted mb-0 text-break">{{ deletionImpact }}</p>
    </template>
    <template v-else-if="deletionDisplay">
      <p class="text-break">确认删除核准检测项目“{{ 'item' in deletionDisplay ? deletionDisplay.item : '' }}”（{{ deletionDisplay.code }}）？</p>
      <p class="text-muted mb-0 text-break">所属上岗证：{{ deletionDisplay.name }} · {{ deletionDisplay.number }}</p>
    </template>
    <p v-if="deletionLoading" class="text-muted small mb-0" role="status"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>{{ deleting.kind === 'certificate' ? '正在核对关联记录…' : '正在核对最新信息…' }}</p>
    <ErrorNotice :error="deletionError" :busy="deletionLoading || deletingBusy" retry @retry="openDelete(deleting.kind, deleting.id, true)" />
    <template #footer><button type="button" class="btn btn-light" :disabled="deletingBusy" @click="closeDelete">取消</button><button type="button" class="btn btn-danger" :disabled="deletingBusy || deletionLoading || !deletionTarget || !!deletionError" @click="confirmDelete">{{ deletingBusy ? '正在删除…' : '确认删除' }}</button></template>
  </BootstrapModal>
  <CertificateFormModal v-if="editor" :kind="editor.kind" :mode="editor.mode" :owner="editor.owner" :record="editor.record" :owner-id="editor.ownerId" :owner-ids="editor.ownerIds" :categories="editorCategories" @close="editor = undefined" @saved="saved" />
  <TemplateToast :message="message" title="操作提示" :tone="messageTone" auto-show />
</template>
