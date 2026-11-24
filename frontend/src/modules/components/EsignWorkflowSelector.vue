<script setup lang="ts">
import { ref } from 'vue'
import ConfirmationModal from '../../components/common/ConfirmationModal.vue'
import type { EsignWorkflow } from '@/services/pipeline'

defineProps<{ busy: boolean; message?: string }>()
const emit = defineEmits<{ close: []; confirm: [mode: EsignWorkflow] }>()
const mode = ref<EsignWorkflow>('legacy')
</script>

<template>
  <ConfirmationModal title="选择报告签署流程" :busy="busy" @close="emit('close')">
    <fieldset :disabled="busy">
      <legend class="visually-hidden">签署流程</legend>
      <label class="d-flex align-items-start gap-2 mb-3">
        <input v-model="mode" type="radio" name="esign-workflow" class="form-check-input flex-shrink-0" value="legacy" />
        <span><strong class="d-block">原流程</strong>报告批准后，集中发起签署。</span>
      </label>
      <label class="d-flex align-items-start gap-2 mb-3">
        <input v-model="mode" type="radio" name="esign-workflow" class="form-check-input flex-shrink-0" value="business_stages_v1" />
        <span><strong class="d-block">分步签署</strong>主检、审核、批准人员分别在各自环节签署。</span>
      </label>
    </fieldset>
    <p class="mb-0">提交后，本报告退回或撤回时仍沿用这次选择。</p>
    <p v-if="message" class="alert alert-warning mt-2 mb-0" role="status">{{ message }}</p>
    <template #footer>
      <button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button>
      <button type="button" class="btn btn-primary" :disabled="busy" @click="emit('confirm', mode)">确认并完成录入</button>
    </template>
  </ConfirmationModal>
</template>
