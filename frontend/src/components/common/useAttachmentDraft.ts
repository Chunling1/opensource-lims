import { computed, inject, markRaw, onBeforeUnmount, provide, reactive, ref, toRaw, type InjectionKey } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { downloadBlob } from '../../services/reports/reportPdf'
import { useUnsavedChanges } from './useUnsavedChanges'
import { useFormChanges } from './useFormChanges'
import type { DemoAttachment } from '../../types/commissions/registration'
import type { UploadProgress } from './fileUploadProgress'

export interface DraftUploadTask {
  id: string; file: File; target: DemoAttachment[]; phase: 'reading' | 'uploading' | 'saving' | 'done' | 'failed'; percent?: number; error: string; controller: AbortController
}
type AttachmentDraft = ReturnType<typeof useAttachmentDraft>
const key: InjectionKey<AttachmentDraft> = Symbol('attachment-draft')
export function useFormAttachments() { const value = inject(key); if (!value) throw new Error('附件需要表单草稿'); return value }
export function useAttachmentDraft(scope: 'personnel' | 'external' | 'certificate' | 'equipment' | 'document' | 'monitoring-document' | 'daily-request', recordId: () => string | undefined, files: () => DemoAttachment[], saving: () => boolean, form?: { value: () => unknown; ready: () => boolean }) {
  const id = crypto.randomUUID(), ownerRecord = recordId() || ''
  const tasks = ref<DraftUploadTask[]>([]), changed = ref(false), operations = ref(0)
  let started = false, disposed = false
  const committed = ref(false)
  const active = computed(() => operations.value > 0 || tasks.value.some(task => !['done', 'failed'].includes(task.phase)))
  const failed = computed(() => tasks.value.some(task => task.phase === 'failed'))
  const blocked = computed(() => active.value || failed.value)
  const formChanges = useFormChanges(form?.value || (() => undefined), form?.ready || (() => false))
  const dirty = computed(() => !committed.value && (changed.value || active.value || saving() || formChanges.dirty.value))
  useUnsavedChanges(dirty)
  const leaveRequested = ref(false)
  let leavePromise: Promise<boolean> | undefined, resolveLeave: ((value: boolean) => void) | undefined
  function finishLeave(leave: boolean) {
    if (leave && saving()) return
    leaveRequested.value = false
    resolveLeave?.(leave); resolveLeave = undefined; leavePromise = undefined
  }
  async function allowLeave() {
    if (saving()) return false
    if (!dirty.value) return true
    if (!leavePromise) {
      leavePromise = new Promise<boolean>(resolve => { resolveLeave = resolve })
      leaveRequested.value = true
    }
    return leavePromise
  }
  onBeforeRouteLeave(allowLeave); onBeforeRouteUpdate(allowLeave)
  function pending(target?: DemoAttachment[]) { return tasks.value.filter(task => task.phase !== 'done' && (!target || toRaw(task.target) === toRaw(target))) }
  async function run(task: DraftUploadTask, notify?: UploadProgress) {
    task.phase = 'reading'; task.error = ''; task.percent = undefined
    const update: UploadProgress = (phase, loaded, total) => {
      task.phase = phase; task.percent = total ? Math.min(100, Math.floor((loaded || 0) / total * 100)) : undefined
      notify?.(phase, loaded, total)
    }
    try {
      const all = [...new Map(files().map(file => [file.id, file])).values()]
      const reserved = tasks.value.filter(t => t.id !== task.id && !['done', 'failed'].includes(t.phase))
      if (all.length + reserved.length >= 100 || all.reduce((sum, f) => sum + f.size, task.file.size) + reserved.reduce((sum, t) => sum + t.file.size, 0) > 20 * 1024 * 1024) throw new Error('附件总计不能超过 20 MB、100 个。')
      const signal = task.controller.signal
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader(), abort = () => reader.abort()
        signal.throwIfAborted(); signal.addEventListener('abort', abort, { once: true })
        reader.onloadend = () => signal.removeEventListener('abort', abort)
        reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(new Error('附件读取失败，请重试。'))
        reader.onabort = () => reject(new DOMException('上传已取消', 'AbortError'))
        reader.onprogress = event => update('reading', event.loaded, event.lengthComputable ? event.total : undefined)
        reader.readAsDataURL(task.file)
      })
      signal.throwIfAborted(); started = true; update('uploading', 0, task.file.size)
      const file = await registrationDemo.uploadDraftAttachment(id, scope, ownerRecord, { id: task.id, name: task.file.name, type: task.file.type, size: task.file.size, dataUrl }, (loaded, total) => update(loaded >= total ? 'saving' : 'uploading', loaded, total), signal)
      if (!disposed && !signal.aborted) { task.target.push(file); changed.value = true; task.phase = 'done' }
    } catch (error) {
      task.phase = 'failed'; task.error = error instanceof Error ? error.message : '上传失败，请重试。'
      throw error
    }
  }
  async function upload(file: File, target: DemoAttachment[], notify: UploadProgress) {
    if (disposed) throw new Error('表单已关闭。')
    const task = reactive<DraftUploadTask>({ id: crypto.randomUUID(), file: markRaw(file), target, phase: 'reading', error: '', controller: markRaw(new AbortController()) })
    tasks.value.push(task); changed.value = true
    await run(task, notify)
  }
  function retry(task: DraftUploadTask) { if (task.phase === 'failed') { task.controller = markRaw(new AbortController()); void run(task).catch(() => {}) } }
  function removeTask(task: DraftUploadTask) { task.controller.abort(); tasks.value = tasks.value.filter(t => t.id !== task.id) }
  function dismissFailed(file: File, target: DemoAttachment[]) { for (const task of pending(target)) if (task.phase === 'failed' && task.file === file) removeTask(task) }
  async function remove(file: DemoAttachment, target: DemoAttachment[]) {
    operations.value++
    try {
      if (!file.dataUrl) await registrationDemo.removeDraftAttachment(id, scope, ownerRecord, file.id)
      const index = target.findIndex(f => f.id === file.id); if (index >= 0) target.splice(index, 1)
      changed.value = true
    } finally { operations.value-- }
  }
  async function download(file: DemoAttachment) {
    if (!file.dataUrl) { downloadBlob(await registrationDemo.draftAttachmentFile(id, scope, ownerRecord, file.id), file.name); return }
    const bytes = atob(file.dataUrl.slice(file.dataUrl.indexOf(',') + 1))
    downloadBlob(new Blob([Uint8Array.from(bytes, c => c.charCodeAt(0))], { type: 'application/octet-stream' }), file.name)
  }
  function payload<T extends object>(value: T): T & { attachmentDraftId?: string } {
    let hasTemporaryFiles = false
    const data = JSON.parse(JSON.stringify(value, (key, item) => {
      if (key !== 'dataUrl') return item
      if (item === '') hasTemporaryFiles = true
      return ''
    }))
    return { ...data, ...(hasTemporaryFiles && started ? { attachmentDraftId: id } : {}) }
  }
  function discard() { if (started) void registrationDemo.discardAttachmentDraft(id, scope, ownerRecord).catch(() => { /* Server expiry also clears interrupted drafts. */ }) }
  function commit() { committed.value = true; changed.value = false; discard() }
  onBeforeUnmount(() => {
    finishLeave(false)
    disposed = true; tasks.value.forEach(task => task.controller.abort())
    if (!committed.value) discard()
  })
  const manager = { tasks, active, failed, blocked, pending, upload, retry, removeTask, dismissFailed, remove, download, allowLeave, leaveRequested, finishLeave, payload, commit }
  provide(key, manager)
  return manager
}
