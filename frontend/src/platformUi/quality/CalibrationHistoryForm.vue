<template>
  <form class="mb-3" @submit.prevent="save">
    <h6>补录历史校准</h6>
    <p class="form-text">用于已经更新过校准信息的仪器。按旧证书及确认记录填写，不改变当前校准日期；两期之间无有效校准的日期仍不可使用。</p>
    <div class="row g-3">
      <div class="col-md-6"><label :for="`${id}-start`" class="form-label">旧校准有效开始日期</label><input :id="`${id}-start`" v-model="draft.start" type="date" class="form-control" required :disabled="saving" /></div>
      <div class="col-md-6"><label :for="`${id}-end`" class="form-label">旧校准有效期至</label><input :id="`${id}-end`" v-model="draft.end" type="date" class="form-control" required :disabled="saving" /></div>
      <div class="col-md-6"><label :for="`${id}-certificate`" class="form-label">旧校准证书编号</label><input :id="`${id}-certificate`" v-model="draft.certificateNo" class="form-control" maxlength="160" required :disabled="saving" /></div>
      <div class="col-md-6"><label :for="`${id}-unit`" class="form-label">校准机构（选填）</label><input :id="`${id}-unit`" v-model="draft.calUnit" class="form-control" maxlength="200" :disabled="saving" /></div>
      <div class="col-12"><label :for="`${id}-reason`" class="form-label">补录依据</label><textarea :id="`${id}-reason`" v-model="draft.reason" class="form-control" minlength="2" maxlength="300" required :disabled="saving" /></div>
    </div>
    <div class="form-check my-3"><input :id="`${id}-confirmed`" v-model="draft.confirmed" type="checkbox" class="form-check-input" required :disabled="saving" /><label :for="`${id}-confirmed`" class="form-check-label">已核对旧校准凭证，确认填写期间符合使用要求</label></div>
    <p v-if="error" class="text-danger" role="alert">{{ error }}</p>
    <p v-if="success" class="text-success" role="status">历史校准已补录，当前校准信息未改变。</p>
    <button type="submit" class="btn btn-primary" :disabled="saving">{{ saving ? '正在补录…' : '保存历史校准' }}</button>
  </form>
</template>
<script setup lang="ts">
import { reactive, ref, useId } from 'vue'
import { backfillEquipmentCalibration } from '@/services/quality'
const props = defineProps<{ equipmentId: number }>()
const emit = defineEmits<{ saved: [] }>()
const id = useId(), saving = ref(false), error = ref(''), success = ref(false)
const empty = () => ({ start: '', end: '', certificateNo: '', calUnit: '', reason: '', confirmed: false })
const draft = reactive(empty())
async function save() {
  if (saving.value) return
  error.value = ''; success.value = false
  if (!draft.confirmed || !draft.start || !draft.end || !draft.certificateNo.trim() || draft.reason.trim().length < 2) { error.value = '请填写起止日期、证书编号和补录依据，并确认已核对凭证。'; return }
  if (draft.end < draft.start) { error.value = '有效期至不得早于开始日期。'; return }
  saving.value = true
  try { await backfillEquipmentCalibration(props.equipmentId, { ...draft }); Object.assign(draft, empty()); success.value = true; emit('saved') }
  catch (e) { error.value = e instanceof Error ? e.message : '补录失败，请稍后重试' }
  finally { saving.value = false }
}
</script>
