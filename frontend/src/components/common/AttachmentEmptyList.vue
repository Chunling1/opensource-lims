<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
const props = defineProps<{ fillAvailable?: boolean; empty: boolean; canAttach: boolean; fileCount: number; emptyLabel?: string; extraMetadata?: boolean }>()
const element = ref<HTMLElement>()
const rows = ref(props.empty || props.fillAvailable ? 1 : 0)
let observer: ResizeObserver | undefined, contentObserver: MutationObserver | undefined, frame = 0, rowHeight = 0
function measure() {
  if (!props.fillAvailable) { rows.value = props.empty ? 1 : 0; return }
  const list = element.value
  const row = list?.querySelector('li')
  const body = list?.closest<HTMLElement>('.modal-body')
  if (!props.fillAvailable || !list || !body) return
  const bounds = list.getBoundingClientRect(), bodyBounds = body.getBoundingClientRect()
  if (row) rowHeight = row.getBoundingClientRect().height
  if (!rowHeight || !body.clientHeight) return
  const paddingBottom = parseFloat(getComputedStyle(body).paddingBottom) || 0
  const gap = parseFloat(getComputedStyle(list).rowGap) || 0
  // Reserve space for any notice below the list, as well as the modal body's padding.
  const contentBottom = Math.max(bounds.bottom, ...Array.from(body.children, child => child.getBoundingClientRect().bottom))
  const followingHeight = contentBottom - bounds.bottom
  const leadingGap = props.empty ? 0 : gap
  const available = body.clientHeight - (bounds.top - bodyBounds.top + body.scrollTop) - paddingBottom - followingHeight - leadingGap
  rows.value = Math.max(0, Math.floor((available + gap - 1) / (rowHeight + gap)))
}
function schedule() {
  cancelAnimationFrame(frame)
  frame = requestAnimationFrame(measure)
}
// Rebalance in the same render cycle as file insertion, before an extra row can flash a scrollbar.
watch(() => props.fileCount, measure, { flush: 'post' })
onMounted(() => {
  if (!props.fillAvailable) return
  const body = element.value?.closest<HTMLElement>('.modal-body')
  observer = new ResizeObserver(schedule)
  if (body) {
    observer.observe(body)
    for (const child of body.children) observer.observe(child)
    contentObserver = new MutationObserver(() => {
      // Upload controls can mount after this list when the modal opens.
      // Observe their later height transitions as completed files leave the queue.
      for (const child of body.children) observer?.observe(child)
      schedule()
    })
    contentObserver.observe(body, { childList: true, subtree: true })
  }
  if (element.value) observer.observe(element.value)
  schedule()
})
onBeforeUnmount(() => { observer?.disconnect(); contentObserver?.disconnect(); cancelAnimationFrame(frame) })
</script>
<template>
  <div class="position-relative overflow-hidden">
    <slot />
    <ul ref="element" class="list-unstyled d-flex flex-column gap-2 mb-0 pe-none fade" :class="{ 'pt-2': !empty && rows > 0, 'opacity-50': empty, 'opacity-100': !empty }" aria-hidden="true" data-attachment-placeholders>
      <!-- Keep one clipped measurement row when no complete row fits, so resizing can restore rows. -->
      <li v-for="row in Math.max(rows, 1)" :key="row" class="border rounded p-3"
        :class="{ 'position-absolute top-0 start-0 w-100 invisible': !rows }" :data-placeholder-probe="!rows ? '' : undefined">
        <div class="d-flex flex-wrap align-items-center gap-2">
          <div class="d-flex align-items-center gap-3 col overflow-hidden">
            <div class="avatar-sm flex-shrink-0"><span class="avatar bg-light text-muted rounded fs-1 opacity-75"><i class="ti ti-file-text"></i></span></div>
            <div class="flex-grow-1 overflow-hidden">
              <template v-if="extraMetadata">
                <div class="btn p-0 border-0 d-block text-start"><span class="placeholder placeholder-sm bg-secondary opacity-25 rounded col-5"></span></div>
                <div class="small mt-1"><span class="placeholder placeholder-xs bg-secondary opacity-25 rounded col-3"></span></div>
                <div class="d-flex small mt-1"><span class="badge invisible">上传文件</span></div>
              </template>
              <template v-else>
              <span class="placeholder placeholder-sm bg-secondary opacity-25 rounded col-5 d-block mb-2"></span>
              <span class="placeholder placeholder-xs bg-secondary opacity-25 rounded col-3 d-block"></span>
              </template>
            </div>
          </div>
          <div class="col-12 col-sm-auto d-flex justify-content-end gap-2">
            <span class="btn btn-sm btn-light opacity-75"><span class="invisible"><i class="ti ti-download me-1"></i>下载</span></span>
            <span v-if="canAttach" class="btn btn-sm btn-light opacity-75"><span class="invisible"><i class="ti ti-trash me-1"></i>删除</span></span>
          </div>
        </div>
      </li>
    </ul>
    <Transition enter-active-class="fade" enter-from-class="opacity-0" enter-to-class="opacity-100" leave-active-class="fade" leave-from-class="opacity-100" leave-to-class="opacity-0">
      <div v-if="empty && rows" class="position-absolute top-0 start-0 w-100 h-100 d-flex flex-column align-items-center justify-content-center text-muted pe-none" role="status" data-attachment-empty-message>
        <i class="ti ti-folder-open fs-36 d-block lh-1 mb-2" aria-hidden="true"></i>
        <p class="mb-0">{{ emptyLabel || '暂无附件' }}</p>
      </div>
    </Transition>
    <p v-if="empty && !rows" class="mb-0 text-center text-muted" role="status">{{ emptyLabel || '暂无附件' }}</p>
  </div>
</template>
