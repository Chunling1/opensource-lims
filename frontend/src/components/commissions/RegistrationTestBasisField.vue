<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import TemplateToast from '../common/TemplateToast.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { basisLabel, joinBasisText, readBasisSeparators, validBasisSeparator } from '../../services/commissions/testBasisText'
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import type { TestBasisSelection, TestBasisStandard } from '../../types/commissions/testBasis'

const props = withDefaults(defineProps<{ planId: string; ids: string[]; separators: string[]; englishBookMarks: boolean; label?: string; fieldId?: string; disabled?: boolean; readonly?: boolean; textValue?: string; textareaRows?: number }>(), { label: '检测依据', fieldId: 'sample-test-basis', textareaRows: 1 })
const emit = defineEmits<{ select: [TestBasisSelection]; open: []; clear: []; pending: [boolean] }>()
const rows = ref<TestBasisStandard[]>([]), loading = ref(false), error = ref<ErrorValue>('')
const field = ref<HTMLTextAreaElement>(), toast = ref<InstanceType<typeof TemplateToast>>()
const labels = computed(() => rows.value.map(row => basisLabel(row, props.englishBookMarks)))
const text = computed(() => props.readonly && props.textValue !== undefined ? props.textValue : joinBasisText(labels.value, props.separators))
const editMessage = computed(() => `只能修改${props.label}之间的分隔符，每处最多 2 个符号、空格或换行；增删项目请使用选择列表。`)
const missingMessage = computed(() => `请在每两项${props.label}之间填写分隔符。`)
let controller: AbortController | undefined, sequence = 0, composing = false, cursor = [0, 0]
function cancel() { sequence++; controller?.abort(); composing = false; loading.value = false; emit('pending', false) }
async function load() {
  cancel(); const token = sequence, active = controller = new AbortController()
  rows.value = []; error.value = ''
  if (props.readonly && props.textValue !== undefined || !props.planId || !props.ids.length || props.disabled) return
  loading.value = true; emit('pending', true)
  try {
    const result = await registrationDemo.testBases({ planId: props.planId, ids: [...props.ids], page: 1, pageSize: 50 }, active.signal)
    if (token !== sequence) return
    const byId = new Map(result.items.map(row => [row.id, row]))
    if (props.ids.some(id => !byId.has(id))) throw new AppError('NOT_FOUND', `部分${props.label}已不可访问，请重新选择。`)
    rows.value = props.ids.map(id => byId.get(id)!)
  } catch (e) { if (token === sequence && !active.signal.aborted) error.value = normalizeError(e) }
  finally { if (token === sequence) { loading.value = false; emit('pending', false) } }
}
function beforeInput() {
  if (!composing && field.value) cursor = [field.value.selectionStart, field.value.selectionEnd]
}
function edit(event: Event) {
  if (composing || props.disabled || props.readonly) return
  const input = event.target as HTMLTextAreaElement
  const separators = readBasisSeparators(input.value, labels.value)
  if (separators === null) {
    input.value = text.value; input.setSelectionRange(cursor[0]!, cursor[1]!)
    toast.value?.show(); return
  }
  emit('select', { ids: [...props.ids], separators, text: input.value, englishBookMarks: props.englishBookMarks })
  input.setCustomValidity(separators.some(value => !validBasisSeparator(value)) ? missingMessage.value : '')
}
function compositionStart() { beforeInput(); composing = true; emit('pending', true) }
function compositionEnd(event: CompositionEvent) { composing = false; edit(event); emit('pending', loading.value) }
watch(() => JSON.stringify([props.planId, props.ids, props.disabled, props.readonly, props.readonly ? props.textValue : undefined, currentActor.value.id]), () => { void load() }, { immediate: true })
watch(() => [text.value, props.separators], async () => {
  await nextTick()
  field.value?.setCustomValidity(props.separators.some(value => !validBasisSeparator(value)) ? missingMessage.value : '')
})
onBeforeUnmount(cancel)
</script>

<template>
  <div role="group" :aria-labelledby="`${fieldId}-label`">
    <slot name="label" :label-id="`${fieldId}-label`"><label :id="`${fieldId}-label`" :for="fieldId" class="form-label">{{ label }}</label></slot>
    <div class="input-group">
      <textarea :id="fieldId" ref="field" class="form-control" :class="{ 'bg-body-tertiary': readonly }" :rows="textareaRows" :aria-labelledby="`${fieldId}-label`" :value="text" :disabled="disabled || !planId" :readonly="readonly || loading || !!error || !ids.length" :aria-busy="loading" :placeholder="!planId ? '请先选择检测方案' : loading ? `正在加载${label}…` : `请选择${label}`" @beforeinput="beforeInput" @input="edit" @compositionstart="compositionStart" @compositionend="compositionEnd"></textarea>
      <button class="btn btn-light" type="button" v-if="!readonly" :aria-label="`选择${label}`" :disabled="disabled || !planId || loading" @click="emit('open')"><i class="ti ti-search" aria-hidden="true"></i></button>
      <button v-if="ids.length && !readonly" class="btn btn-light" type="button" :aria-label="`清除${label}`" :disabled="disabled || loading" @click="emit('clear')"><i class="ti ti-x" aria-hidden="true"></i></button>
    </div>
    <ErrorNotice class="mt-2 mb-0" :error="error" retry :busy="loading" @retry="load" />
    <TemplateToast ref="toast" :message="editMessage" tone="danger" />
  </div>
</template>
