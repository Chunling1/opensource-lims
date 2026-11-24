<script setup lang="ts" generic="T extends Omit<DemoAttachment, 'dataUrl'>">
import { computed } from 'vue'
import AttachmentEmptyList from './AttachmentEmptyList.vue'
import type { DemoAttachment } from '../../types/commissions/registration'
const props = withDefaults(defineProps<{ files: T[]; canAttach: boolean; busy: boolean; fillEmpty?: boolean; title?: string; emptyLabel?: string; selectedIds?: string[]; canRemove?: (file: T) => boolean }>(), { title: '附件列表', emptyLabel: '暂无附件' })
defineEmits<{ download: [T]; remove: [T] }>()
const totalSize = computed(() => props.files.reduce((sum, file) => sum + file.size, 0))
function size(bytes: number) { return bytes < 1024 ? `${bytes} B` : bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB` }
function appearance(file: T) {
  const extension = file.name.split('.').pop()?.toLowerCase()
  if (extension === 'pdf' || file.type === 'application/pdf') return { icon: 'ti ti-file-type-pdf', tone: 'text-danger', label: 'PDF 文档' }
  if (['doc', 'docx'].includes(extension || '')) return { icon: 'ti ti-file-word', tone: 'text-primary', label: 'Word 文档' }
  if (['xls', 'xlsx', 'csv'].includes(extension || '')) return { icon: 'ti ti-file-spreadsheet', tone: 'text-success', label: '电子表格' }
  if (file.type.startsWith('image/') || ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'].includes(extension || '')) return { icon: 'ti ti-photo', tone: 'text-info', label: '图片' }
  if (['zip', 'rar', '7z', 'gz'].includes(extension || '')) return { icon: 'ti ti-file-zip', tone: 'text-warning', label: '压缩文件' }
  return { icon: 'ti ti-file-text', tone: 'text-secondary', label: '文件' }
}
</script>
<template>
  <div>
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
      <div class="d-flex align-items-center gap-2"><slot name="header-leading" /><h6 class="mb-0"><slot name="title">{{ title }}</slot><span class="badge bg-primary-subtle text-primary ms-2">{{ files.length }}</span></h6></div>
      <span class="text-muted small ms-auto">共 {{ size(totalSize) }}</span>
      <div v-if="$slots.toolbar" class="d-flex flex-wrap align-items-center gap-2"><slot name="toolbar" /></div>
    </div>
    <AttachmentEmptyList :fill-available="fillEmpty" :empty="!files.length" :can-attach="canAttach" :file-count="files.length" :empty-label="emptyLabel" :extra-metadata="!!$slots.metadata">
    <TransitionGroup tag="ul" class="list-unstyled d-flex flex-column gap-2 mb-0" enter-active-class="fade" enter-from-class="opacity-0" enter-to-class="opacity-100">
      <li v-for="file in files" :key="file.id" class="border rounded p-3" :class="{ 'bg-light border-primary': selectedIds?.includes(file.id) }" data-attachment-file>
        <div class="d-flex flex-wrap align-items-center gap-2">
          <slot name="leading" :file="file" />
          <div class="d-flex align-items-center gap-3 col overflow-hidden">
            <div class="avatar-sm flex-shrink-0"><span class="avatar bg-light rounded fs-1" :class="appearance(file).tone"><i :class="appearance(file).icon" aria-hidden="true"></i></span></div>
            <div class="flex-grow-1 overflow-hidden">
              <slot name="name" :file="file"><button type="button" class="btn btn-link text-body fw-medium p-0 text-start text-break" :disabled="busy" @click="!busy && $emit('download', file)">{{ file.name }}</button></slot>
              <div class="text-muted small mt-1">{{ appearance(file).label }}<span class="mx-2" aria-hidden="true">·</span>{{ size(file.size) }}<slot name="details" :file="file" /></div>
              <slot name="metadata" :file="file" />
            </div>
          </div>
          <div class="col-12 col-sm-auto d-flex flex-wrap justify-content-end gap-2">
            <slot name="download" :file="file">
            <button type="button" class="btn btn-sm btn-primary-lt" :aria-label="`下载附件 ${file.name}`" :disabled="busy" @click="!busy && $emit('download', file)"><i class="ti ti-download me-1" aria-hidden="true"></i>下载</button>
            </slot>
            <slot name="actions" :file="file" />
            <button v-if="canAttach && (!canRemove || canRemove(file))" type="button" class="btn btn-sm btn-danger-lt" :aria-label="`删除附件 ${file.name}`" :disabled="busy" @click="!busy && canAttach && $emit('remove', file)"><i class="ti ti-trash me-1" aria-hidden="true"></i>删除</button>
          </div>
        </div>
      </li>
    </TransitionGroup>
    </AttachmentEmptyList>
  </div>
</template>
