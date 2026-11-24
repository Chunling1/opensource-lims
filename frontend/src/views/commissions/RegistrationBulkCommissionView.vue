<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import LoadState from '../../components/common/LoadState.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import { useUnsavedChanges } from '../../components/common/useUnsavedChanges'
import RegistrationCommissionFields from '../../components/commissions/RegistrationCommissionFields.vue'
import { registrationDemo as api } from '../../services/commissions/registrationApi'
import { registrationReturn, registrationContext } from '../../services/commissions/registrationService'
import { bulkCommissionFields } from '../../types/commissions/commissionFields'
import { emptySampleCommission, type SampleCommissionInfo } from '../../types/commissions/sampleCommission'
import type { BulkCommissionContext } from '../../types/commissions/bulkCommission'
import { isOperationalError, normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'

const route = useRoute(), returnTo = computed(() => registrationReturn(route.query.returnTo, registrationContext(route.path).root))
const ids = computed(() => typeof route.query.ids === 'string' ? [...new Set(route.query.ids.split(',').filter(Boolean))] : [])
const context = ref<BulkCommissionContext>(), form = reactive(emptySampleCommission())
const selected = ref<string[]>([]), mixed = ref<string[]>([])
const loading = ref(false), busy = ref(false), sourcing = ref(false), loadError = ref<ErrorValue>(''), error = ref<ErrorValue>('')
const success = ref(''), successToast = ref<InstanceType<typeof TemplateToast>>(), errorToast = ref<InstanceType<typeof TemplateToast>>()
const confirmSave = ref(false), confirmReload = ref(false), confirmLeave = ref(false)
const selectedFields = computed(() => bulkCommissionFields.filter(field => selected.value.includes(field.key)))
const allSelected = computed(() => selected.value.length === bulkCommissionFields.length)
const snapshot = () => JSON.stringify({ form, selected: selected.value })
const baseline = ref(''), dirty = computed(() => !!baseline.value && snapshot() !== baseline.value)
useUnsavedChanges(dirty)
let epoch = 0, resolveLeave: ((value: boolean) => void) | undefined
function toggleField(key: string, enabled: boolean) { selected.value = enabled ? [...new Set([...selected.value, key])] : selected.value.filter(value => value !== key) }
async function showError(e: unknown) { error.value = normalizeError(e); await nextTick(); errorToast.value?.show() }
async function load() {
  const token = ++epoch; loading.value = true; loadError.value = ''; baseline.value = ''; context.value = undefined; selected.value = []; mixed.value = []; errorToast.value?.hide()
  try {
    const result = await api.bulkCommissionContext(ids.value, registrationContext(route.path).workspace)
    if (token !== epoch) return
    context.value = result
    const empty = emptySampleCommission()
    for (const key of Object.keys(empty) as (keyof SampleCommissionInfo)[]) {
      const first = result.items[0]!.commissionInfo[key] ?? ''
      const same = result.items.every(row => (row.commissionInfo[key] ?? '') === first)
      empty[key] = same ? first : ''
      if (!same) mixed.value.push(key)
    }
    Object.assign(form, empty); baseline.value = snapshot()
  } catch (e) { if (token === epoch) loadError.value = normalizeError(e) }
  finally { if (token === epoch) loading.value = false }
}
async function fromCommission() {
  if (!selected.value.length || sourcing.value || busy.value) return
  const token = epoch, fields = [...selected.value]; sourcing.value = true
  try {
    const source = await api.bulkCommissionSource(ids.value, registrationContext(route.path).workspace)
    if (token !== epoch) return
    for (const field of fields) {
      const keys = field === 'contract' ? ['contractId', 'contract', 'erpContract', 'erpProjectType'] : [field]
      for (const key of keys as (keyof SampleCommissionInfo)[]) form[key] = source[key] ?? ''
    }
  } catch (e) { if (token === epoch) await showError(e) }
  finally { if (token === epoch) sourcing.value = false }
}
async function save() {
  if (!context.value || busy.value || sourcing.value || !selected.value.length) return
  const token = epoch; busy.value = true; errorToast.value?.hide()
  const changes = Object.fromEntries(selectedFields.value.map(field => { const key = field.key === 'contract' ? 'contractId' : field.key; return [key, String(form[key as keyof SampleCommissionInfo] ?? '')] }))
  try {
    const result = await api.saveBulkCommission(context.value.items.map(({ id, version }) => ({ id, version })), changes, registrationContext(route.path).workspace)
    if (token !== epoch) return
    for (const item of context.value.items) item.version = result.items.find(row => row.id === item.id)!.version
    mixed.value = mixed.value.filter(key => !selected.value.includes(key) && !(selected.value.includes('contract') && ['contractId', 'erpContract', 'erpProjectType'].includes(key))); selected.value = []; baseline.value = snapshot()
    success.value = `已更新 ${result.count} 张样品单的委托信息。`; await nextTick(); successToast.value?.show()
  } catch (e) { if (token === epoch) await showError(e) }
  finally { if (token === epoch) { busy.value = false; confirmSave.value = false } }
}
function guard() { if (busy.value || sourcing.value) return false; if (!dirty.value) return true; confirmLeave.value = true; return new Promise<boolean>(resolve => { resolveLeave = resolve }) }
function leave(value: boolean) { confirmLeave.value = false; if (value) baseline.value = ''; resolveLeave?.(value); resolveLeave = undefined }
onBeforeRouteLeave(guard)
onBeforeRouteUpdate(guard)
watch([ids, () => currentActor.value.id], () => { busy.value = false; sourcing.value = false; confirmSave.value = false; confirmReload.value = false; leave(false); void load() }, { immediate: true })
onBeforeUnmount(() => { ++epoch; resolveLeave?.(false) })
</script>
<template>
  <PageHeading title="批量修改委托信息" :parent-to="returnTo" />
  <RouterLink class="btn btn-light mb-3" :to="returnTo"><i class="ti ti-arrow-left me-1" aria-hidden="true"></i>返回{{ registrationContext(route.path).title }}</RouterLink>
  <LoadState :loading="loading" :error="loadError" :back-to="returnTo" @retry="load" />
  <template v-if="context && !loading && !loadError">
    <section class="card" aria-label="批量修改操作区">
      <div class="card-body py-3">
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-3">
          <div class="d-flex flex-wrap align-items-center gap-2"><span class="text-muted">所属委托</span><strong>{{ context.commissionCode }}</strong><span class="badge bg-primary-subtle text-primary">已选 {{ context.items.length }} 张样品</span></div>
          <div class="d-flex flex-wrap align-items-center gap-3">
            <div class="form-check mb-0"><input id="bulk-all" class="form-check-input" type="checkbox" :disabled="busy || sourcing" :checked="allSelected" :indeterminate="selected.length > 0 && !allSelected" @change="selected = allSelected ? [] : bulkCommissionFields.map(field => field.key)" /><label for="bulk-all" class="form-check-label text-nowrap">全选</label></div>
            <button class="btn btn-light text-nowrap" :disabled="!selected.length || busy || sourcing" @click="fromCommission"><i class="ti ti-download me-1" aria-hidden="true"></i>{{ sourcing ? '正在获取…' : '从委托获取' }}</button>
          </div>
        </div>
        <details class="mt-3"><summary class="text-primary">查看所选样品</summary><div class="d-flex flex-wrap gap-2 mt-2"><span v-for="item in context.items" :key="item.id" class="badge bg-light text-body">{{ item.code }}</span></div></details>
      </div>
    </section>
    <fieldset :disabled="busy || sourcing"><RegistrationCommissionFields :form="form" :code="form.code" :owner="form.owner" sample :bulk-fields="selected" :mixed-fields="mixed" @toggle-field="toggleField" /></fieldset>
    <div class="d-flex justify-content-end gap-2 mb-4"><RouterLink class="btn btn-light" :to="returnTo">取消</RouterLink><button class="btn btn-primary" :disabled="!selected.length || busy || sourcing" @click="confirmSave = true">保存</button></div>
  </template>
  <BootstrapModal :open="confirmSave" title="确认批量修改" :busy="busy" scrollable @close="confirmSave = false"><p>将更新 {{ context?.items.length }} 张样品单的以下字段：</p><ul class="list-group"><li v-for="field in selectedFields" :key="field.key" class="list-group-item text-break"><strong>{{ field.label }}：</strong>{{ String(form[field.key as keyof SampleCommissionInfo] ?? '').trim() || '（清空）' }}</li></ul><template #footer><button class="btn btn-light" :disabled="busy" @click="confirmSave = false">返回修改</button><button class="btn btn-primary" :disabled="busy" @click="save">{{ busy ? '正在保存…' : '确认保存' }}</button></template></BootstrapModal>
  <BootstrapModal :open="confirmLeave" title="离开当前页面？" @close="leave(false)"><p>尚有未保存的批量修改，离开后将丢失。</p><template #footer><button class="btn btn-light" @click="leave(false)">继续编辑</button><button class="btn btn-danger" @click="leave(true)">放弃修改并离开</button></template></BootstrapModal>
  <BootstrapModal :open="confirmReload" title="重新加载样品？" @close="confirmReload = false"><p>重新加载将清除当前未保存的字段设置。</p><template #footer><button class="btn btn-light" @click="confirmReload = false">取消</button><button class="btn btn-primary" @click="confirmReload = false; load()">确认重新加载</button></template></BootstrapModal>
  <TemplateToast ref="successToast" :message="success" tone="success" />
  <TemplateToast ref="errorToast" message="" :title="isOperationalError(error) ? '操作提示' : '系统提示'" :tone="isOperationalError(error) ? 'warning' : 'danger'" :autohide="false"><ErrorNotice compact :error="error" /><button v-if="error && error.code !== 'VALIDATION'" class="btn btn-link p-0" :disabled="busy" @click="confirmReload = true">重新加载样品</button></TemplateToast>
</template>
