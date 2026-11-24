<script setup lang="ts">
import FeedbackNotice from './FeedbackNotice.vue'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { AttachmentUploader, UploadProgress } from './fileUploadProgress'
const props = defineProps<{ upload: AttachmentUploader; disabled?: boolean; local?: boolean; label?: string; accept?: string; hint?: string; describedby?: string; maxSize?: number; multiple?: boolean; successLabel?: string; beforeUpload?: (file: File) => Promise<boolean> }>()
const emit = defineEmits<{ discard: [File] }>()
interface PondFile { id: string; file: File }
interface Pond { element: HTMLElement; destroy(): void; setOptions(options: Record<string, unknown>): void; removeFile(id: string): Promise<void>; getFiles(): PondFile[] }
const input = ref<HTMLInputElement>(), unavailable = ref(false)
const fileState = ref(''), failed = ref(false), hasUpload = ref(false)
const queuedCount = ref(0)
const failureMessage = ref('上传失败，点击重试')
let pond: Pond | undefined, alive = true, observer: MutationObserver | undefined
let sizeObserver: ResizeObserver | undefined, lastWidth = 0
const successTimers = new Map<string, ReturnType<typeof setTimeout>>()
const fileErrors = new Map<string, string>()
function clearSuccessTimer() {
  successTimers.forEach(clearTimeout)
  successTimers.clear()
}
const escapeHtml = (text: string) => text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;')
const limit = () => props.maxSize ?? 20 * 1024 * 1024
function validation(file: File) {
  if (!file.size) return '请选择非空文件'
  if (file.size > limit()) return `文件超过 ${limit() / 1024 / 1024} MB`
  if (props.accept && !props.accept.split(',').some(extension => file.name.toLowerCase().endsWith(extension.trim().toLowerCase()))) return `仅支持 ${props.accept.replaceAll('.', '').toUpperCase().replaceAll(',', ' / ')} 文件`
  return ''
}
function resetUpload() {
  const file = pond?.getFiles()[0]
  if (file && !props.disabled && failed.value) void pond?.removeFile(file.id)
}
function labelInput() {
  const browser = pond?.element.querySelector('input[type="file"]')
  browser?.removeAttribute('aria-labelledby')
  browser?.setAttribute('aria-label', props.label || '添加附件（最大 20 MB）')
  if (props.accept) browser?.setAttribute('accept', props.accept)
  if (props.describedby) browser?.setAttribute('aria-describedby', props.describedby)
  pond?.element.querySelector('.filepond--drop-label label')?.classList.add('w-100', 'p-3')
  // Removed items remain in FilePond's DOM during their exit animation.
  // Restore the chooser from the live queue immediately, without waiting for that DOM cleanup.
  queuedCount.value = pond?.getFiles().length || 0
  const hasFiles = queuedCount.value > 0
  hasUpload.value = hasFiles
  fileState.value = pond?.element.querySelector<HTMLElement>('.filepond--item')?.dataset.filepondItemState || ''
  failed.value = /error|invalid/.test(fileState.value)
  pond?.element.classList.add('h-100', 'm-0', 'border-0', 'bg-transparent', 'rounded', 'fs-5')
  if (props.multiple && queuedCount.value > 1) pond?.element.classList.remove('h-100')
  const dropLabel = pond?.element.querySelector<HTMLElement>('.filepond--drop-label')
  if (dropLabel) {
    dropLabel.classList.add('h-100', 'w-100', 'top-50', 'translate-middle-y', 'border', 'border-dashed', 'rounded-3', 'bg-light', 'fade')
    dropLabel.classList.toggle('opacity-0', hasFiles)
    dropLabel.classList.toggle('opacity-100', !hasFiles)
    dropLabel.classList.toggle('pe-none', hasFiles)
    dropLabel.inert = hasFiles
    dropLabel.setAttribute('aria-hidden', String(hasFiles))
  }
  pond?.element.querySelectorAll('.filepond--panel-root').forEach(panel => {
    panel.classList.add('border-0', 'bg-transparent')
  })
  pond?.element.querySelector('.filepond--list')?.classList.add('start-0', 'end-0', 'h-100')
  const list = pond?.element.querySelector<HTMLElement>('.filepond--list-scroller')
  list?.classList.add('my-0', 'h-100', 'top-50', 'translate-middle-y', 'fade', 'overflow-visible')
  list?.classList.toggle('opacity-0', !hasFiles)
  list?.classList.toggle('opacity-100', hasFiles)
  list?.classList.toggle('pe-none', !hasFiles)
  if (list) {
    list.inert = !hasFiles
    // A single file fills this fixed stage; FilePond's scrolling mask would clip its bottom edge.
    list.removeAttribute('data-state')
  }
  if (props.multiple) {
    dropLabel?.classList.remove('h-100', 'top-50', 'translate-middle-y')
    dropLabel?.classList.add('avatar-md')
    dropLabel?.classList.toggle('d-none', hasFiles)
    pond?.element.querySelector('.filepond--list')?.classList.remove('h-100')
    list?.classList.remove('h-100', 'top-50', 'translate-middle-y')
  }
  pond?.element.querySelectorAll<HTMLElement>('.filepond--item').forEach(item => {
    const state = item.dataset.filepondItemState || ''
    const color = /error|invalid/.test(state) ? 'danger' : state === 'processing-complete' ? 'success' : 'primary'
    // Paint translucent theme colors once; overlapping panel segments otherwise form dark seams.
    item.classList.remove('bg-primary-subtle', 'bg-success-subtle', 'bg-danger-subtle')
    item.classList.add(`bg-${color}-subtle`, 'rounded-3', 'm-0', 'h-100', 'top-50', 'translate-middle-y')
    if (props.multiple) {
      item.classList.remove('h-100', 'top-50', 'translate-middle-y', 'm-0')
      item.classList.add('avatar-md', 'w-100', 'mx-0', 'mt-0', 'mb-2')
      const surface = item.querySelector('.filepond--file')
      if (!surface) return
      surface.classList.add('avatar-md', 'w-100')
      let icon = surface.querySelector<HTMLElement>('[data-upload-state-icon]')
      if (!icon) { icon = document.createElement('i'); icon.dataset.uploadStateIcon = ''; icon.setAttribute('aria-hidden', 'true'); surface.append(icon) }
      icon.className = `position-absolute start-0 top-50 translate-middle-y ms-3 fs-1 lh-1 pe-none ${color === 'danger' ? 'ti ti-alert-circle' : color === 'success' ? 'ti ti-circle-check' : 'ti ti-file-upload'} text-${color}-emphasis`
      let retry = surface.querySelector<HTMLButtonElement>('[data-upload-retry]')
      if (color === 'danger' && !retry) {
        retry = document.createElement('button'); retry.type = 'button'; retry.dataset.uploadRetry = ''
        retry.className = 'btn position-absolute top-0 start-0 w-100 h-100 p-0 border-0 bg-transparent rounded-3 focus-ring'
        retry.addEventListener('click', () => { const file = pond?.getFiles().find(file => item.id.endsWith(file.id)); if (file && !props.disabled) void pond?.removeFile(file.id) })
        surface.append(retry)
      }
      if (color !== 'danger') retry?.remove()
      if (retry) retry.disabled = !!props.disabled
    }
    item.querySelector('.filepond--file')?.classList.add('align-items-center')
    item.querySelectorAll<HTMLElement>('.filepond--item-panel, [data-upload-panel]').forEach(panel => {
      // The template forces the item-panel class to primary with !important.
      // Retain FilePond's structural panel classes and use theme utilities for its color.
      panel.dataset.uploadPanel = ''
      panel.classList.remove('filepond--item-panel')
      panel.classList.add('bg-transparent', 'rounded-3', 'shadow-none')
    })
    // Keep both text blocks anchored while FilePond animates between processing and completion.
    item.querySelector('.filepond--file-info')?.classList.add('text-body', 'position-absolute', 'top-50', 'start-0', 'translate-middle-y', 'w-50', 'ps-5', 'pe-3', 'm-0')
    item.querySelector('.filepond--processing-complete-indicator')?.classList.add('d-none')
    item.querySelectorAll('.filepond--file-info-main, .filepond--file-status-main').forEach(label => label.classList.add('fs-5'))
    item.querySelectorAll('.filepond--file-info-sub, .filepond--file-status-sub').forEach(label => label.classList.add('small'))
    item.querySelector('.filepond--file-info-sub')?.classList.add('opacity-100', 'text-muted')
    item.querySelectorAll('.filepond--file-status, .filepond--progress-indicator, .filepond--processing-complete-indicator, .filepond--file-action-button').forEach(element => {
      element.classList.remove('text-primary-emphasis', 'text-success-emphasis', 'text-danger-emphasis')
      element.classList.add(`text-${color}-emphasis`)
    })
    item.querySelectorAll('.filepond--progress-indicator, .filepond--processing-complete-indicator, .filepond--file-action-button').forEach(element => element.classList.add('top-50', 'translate-middle-y'))
    item.querySelectorAll('.filepond--file-action-button').forEach(button => button.classList.add('bg-transparent', 'focus-ring'))
    item.querySelectorAll('.filepond--action-remove-item, .filepond--action-retry-item-processing, .filepond--action-retry-item-load').forEach(button => button.classList.add('d-none'))
    item.querySelector('.filepond--file-status')?.classList.add('position-absolute', 'top-50', 'end-0', 'translate-middle-y', 'w-50', 'me-3', 'pe-4')
    item.querySelector('.filepond--file-status')?.classList.toggle('pe-4', !/error|invalid/.test(state))
    item.querySelector('.filepond--file-status-sub')?.classList.add('d-none')
    item.querySelectorAll<HTMLElement>('.filepond--file-status-main').forEach(label => {
      const isFailed = /error|invalid/.test(state)
      const fileId = pond?.getFiles().find(file => item.id.endsWith(file.id))?.id
      const ownError = fileId ? fileErrors.get(fileId) : undefined
      const reason = (ownError || label.textContent || '上传失败').replace(/[，,。\s]*点击重试$/, '').replace(/[，,。\s]*请重试[。\s]*$/, '').replace(/[，,。\s]+$/, '')
      if (isFailed && (!label.querySelector('[data-upload-retry-hint]') || label.textContent !== `${reason}，点击重试`)) {
        label.textContent = `${reason}，`
        const hint = document.createElement('span')
        hint.classList.add('text-nowrap')
        hint.dataset.uploadRetryHint = ''
        hint.textContent = '点击重试'
        label.append(hint)
      }
      label.classList.add('w-100')
      label.classList.toggle('text-truncate', !isFailed)
      label.classList.toggle('text-wrap', isFailed)
      if (isFailed) failureMessage.value = label.textContent || '上传失败，点击重试'
      item.querySelector('[data-upload-retry]')?.setAttribute('aria-label', label.textContent || '上传失败，点击重试')
      label.title = label.textContent || ''
    })
  })
}
onMounted(() => {
  const api = (window as unknown as { FilePond?: { create(input: HTMLInputElement, options: Record<string, unknown>): Pond } }).FilePond
  if (!api) { unavailable.value = true; return }
  pond = api.create(input.value!, {
    allowMultiple: !!props.multiple, maxParallelUploads: 1, allowReplace: false, allowRevert: false, allowPaste: false,
    beforeAddFile: (item: { file: File }) => {
      if (!alive) return false
      if (validation(item.file) || !props.beforeUpload) return true
      pond?.setOptions({ labelFileLoading: '等待确认' })
      return props.beforeUpload(item.file).finally(() => { if (alive) pond?.setOptions({ labelFileLoading: '正在读取' }) })
    },
    allowProcess: true, allowMinimumUploadDuration: false,
    disabled: props.disabled, credits: false,
    labelIdle: `<span class="filepond--label-action d-flex align-items-center justify-content-center gap-3 text-decoration-none" role="button" aria-label="上传附件"><i class="ti ti-cloud-upload fs-1 lh-1 text-primary flex-shrink-0" aria-hidden="true"></i><span class="text-start"><span class="d-block fs-5 fw-medium text-body mb-1">拖拽文件到此处，或<span class="text-primary">点击上传</span></span><span class="d-block small text-muted fw-normal">${escapeHtml(props.hint || `单个文件最大 ${limit() / 1024 / 1024} MB`)}</span></span></span>`,
    labelFileLoading: '正在读取', labelFileLoadError: '文件读取失败', labelFileProcessing: '正在处理',
    labelFileProcessingComplete: props.successLabel || '上传成功', labelFileProcessingError: '处理失败',
    labelTapToRetry: '', labelTapToCancel: '', labelTapToUndo: '',
    labelButtonRemoveItem: '移除待上传文件', labelButtonAbortItemLoad: '取消读取',
    labelButtonRetryItemLoad: '重新读取', labelButtonRetryItemProcessing: '重试上传',
    labelButtonProcessItem: '上传文件', labelButtonAbortItemProcessing: '正在处理',
    server: { fetch: null, revert: null, restore: null, load: null,
      process: (_name: string, file: File, _metadata: unknown, load: (id: string) => void, error: (message: string) => void, progress: (computable: boolean, loaded: number, total: number) => void) => {
        const fail = (message: string) => {
          const item = pond?.getFiles().find(item => item.file === file)
          if (item) fileErrors.set(item.id, message)
          pond?.setOptions({ labelFileProcessingError: message })
          error(message)
        }
        if (props.disabled) { fail('当前不可上传附件'); return }
        const invalid = validation(file)
        if (invalid) { fail(invalid); return }
        const report: UploadProgress = (phase, loaded, total) => {
          if (!alive) return
          pond?.setOptions({ labelFileProcessing: { reading: '正在读取', uploading: '正在上传', saving: '正在保存' }[phase] })
          progress(total !== undefined && total > 0, loaded || 0, total || 0)
        }
        report('reading')
        props.upload(file, report).then(() => { if (alive) load(crypto.randomUUID()) }).catch(issue => {
          if (alive) fail(issue instanceof Error ? issue.message : '附件处理失败，请重试')
        })
      },
    },
    onaddfilestart: () => {
      if (!props.multiple) clearSuccessTimer()
      pond?.setOptions({ allowReplace: false })
    },
    onremovefile: (_error: unknown, file: PondFile) => { emit('discard', file.file); fileErrors.delete(file.id); labelInput() },
    onprocessfile: (error: unknown, file: PondFile) => {
      if (error || !alive) return
      if (!props.multiple) clearSuccessTimer()
      // A completed file can be replaced immediately while its success feedback remains visible.
      pond?.setOptions({ allowReplace: !props.multiple })
      successTimers.set(file.id, setTimeout(() => {
        successTimers.delete(file.id)
        if (alive) void pond?.removeFile(file.id)
      }, 2500))
    },
  })
  labelInput()
  observer = new MutationObserver(labelInput)
  observer.observe(pond.element, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-filepond-item-state', 'data-state'] })
  if (props.multiple) {
    // FilePond caches each item's initial height. Its supported ratio option keeps queued rows
    // at the same theme avatar-md height as the single-file upload stage, even after resizing.
    sizeObserver = new ResizeObserver(entries => {
      const width = entries[0]?.contentRect.width || 0
      if (width > 0 && width !== lastWidth) {
        lastWidth = width
        pond?.setOptions({ styleItemPanelAspectRatio: parseFloat(getComputedStyle(document.documentElement).fontSize) * 4.5 / width })
      }
    })
    sizeObserver.observe(pond.element)
  }
})
watch(() => props.disabled, disabled => { pond?.setOptions({ disabled }); labelInput() })
watch(() => props.label, labelInput)
onBeforeUnmount(() => { alive = false; clearSuccessTimer(); observer?.disconnect(); sizeObserver?.disconnect(); pond?.destroy() })
</script>
<template>
  <div class="mb-3">
    <FeedbackNotice v-if="unavailable" message="上传组件加载失败，请刷新页面后重试。">上传组件加载失败，请刷新页面后重试。</FeedbackNotice>
    <div v-else class="w-100 position-relative" :class="{ 'avatar-md': !multiple || queuedCount <= 1 }">
      <input ref="input" type="file" aria-label="添加附件（最大 20 MB）" :disabled="disabled" />
      <i v-if="hasUpload && !multiple"
        class="position-absolute start-0 top-50 translate-middle-y ms-3 fs-1 lh-1 pe-none"
        :class="failed ? 'ti ti-alert-circle text-danger-emphasis' : fileState === 'processing-complete' ? 'ti ti-circle-check text-success-emphasis' : 'ti ti-file-upload text-primary-emphasis'"
        aria-hidden="true" data-upload-state-icon></i>
      <button v-if="failed && !multiple" type="button"
        class="btn position-absolute top-0 start-0 w-100 h-100 p-0 border-0 bg-transparent rounded-3 focus-ring"
        :disabled="disabled" :aria-label="failureMessage" @click="resetUpload" data-upload-retry>
        <span class="visually-hidden">{{ failureMessage }}</span>
      </button>
    </div>
  </div>
</template>
