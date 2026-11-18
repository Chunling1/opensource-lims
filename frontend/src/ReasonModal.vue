<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { Modal } from '@tabler/core/dist/js/tabler.esm.min.js'
import type { Person } from './api'
const props = defineProps<{
  title: string
  reasonLabel: string
  targets?: Person[]
  pending: boolean
  error: string
}>()
const emit = defineEmits<{ close: []; confirm: [string, number] }>()
const root = ref<HTMLElement>(),
  box = ref<HTMLTextAreaElement>(),
  reason = ref(''),
  target = ref(''),
  attempt = ref(false)
let modal: ReturnType<typeof Modal.getOrCreateInstance> | undefined
const hidden = () => emit('close')
onMounted(() => {
  const el = root.value!
  modal = Modal.getOrCreateInstance(el, { backdrop: 'static', keyboard: false })
  el.addEventListener('shown.bs.modal', () => box.value?.focus())
  el.addEventListener('hidden.bs.modal', hidden)
  modal.show()
})
onBeforeUnmount(() => {
  root.value?.removeEventListener('hidden.bs.modal', hidden)
  modal?.dispose()
  document.querySelectorAll('.modal-backdrop').forEach((b) => b.remove())
  document.body.classList.remove('modal-open')
  document.body.removeAttribute('style')
})
function close() {
  if (!props.pending) modal?.hide()
}
function confirm() {
  attempt.value = true
  if (!reason.value.trim() || (props.targets && !target.value)) return
  emit('confirm', reason.value.trim(), Number(target.value))
}
</script>
<template>
  <Teleport to="body">
    <div
      ref="root"
      class="modal modal-blur fade"
      tabindex="-1"
      role="dialog"
      aria-modal="true"
      :aria-label="title"
      @keydown.esc="close"
    >
      <div class="modal-dialog modal-dialog-centered" role="document">
        <form class="modal-content" novalidate @submit.prevent="confirm">
          <div class="modal-status bg-primary"></div>
          <div class="modal-header">
            <h3 class="modal-title">{{ title }}</h3>
            <button
              type="button"
              class="btn-close"
              aria-label="关闭"
              :disabled="pending"
              @click="close"
            ></button>
          </div>
          <div class="modal-body">
            <label class="form-label required" for="reason-text">{{ reasonLabel }}</label>
            <textarea
              id="reason-text"
              ref="box"
              v-model="reason"
              rows="3"
              required
              class="form-control"
              :class="{ 'is-invalid': attempt && !reason.trim() }"
            ></textarea>
            <div class="invalid-feedback">请填写{{ reasonLabel }}。</div>
            <template v-if="targets">
              <label class="form-label required mt-3" for="reason-target">接收人</label>
              <select
                id="reason-target"
                v-model="target"
                required
                class="form-select"
                :class="{ 'is-invalid': attempt && !target }"
              >
                <option value="">请选择</option>
                <option v-for="t in targets" :value="String(t.id)" :key="t.id">
                  {{ t.name }}
                </option>
              </select>
              <div class="invalid-feedback">请选择接收人。</div>
            </template>
            <div v-if="error" role="alert" class="alert alert-danger mt-3 mb-0">{{ error }}</div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-link link-secondary me-auto" type="button" :disabled="pending" @click="close">
              取消
            </button>
            <button class="btn btn-primary" :disabled="pending">
              <span v-if="pending" class="spinner-border spinner-border-sm me-2"></span
              >{{ pending ? '处理中…' : '确认' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>
