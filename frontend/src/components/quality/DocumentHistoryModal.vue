<script setup lang="ts">
import { onBeforeUnmount, reactive, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import DataTable from '../common/table/DataTable.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { documentMovementColumns, type DocumentModule, type DocumentMovementKind, type DocumentMovement, type DocumentPage } from '../../types/quality/documentLibrary'
const props = withDefaults(defineProps<{ documentModule?: DocumentModule; kind: DocumentMovementKind; documentId?: string }>(), { documentModule: 'library' })
const movementColumns = documentMovementColumns(props.kind)
const emit = defineEmits<{ close: [] }>()
const title = `${props.documentModule === 'monitoring' ? '质量监控计划' : '文件'}${props.kind === 'issue' ? '领用记录' : '回收记录'}`
const draft = reactive({ category: '', name: '' }), query = reactive({ category: '', name: '', page: 1, pageSize: 10 })
const data = ref<DocumentPage<DocumentMovement>>({ items: [], total: 0, page: 1, pageSize: 10 }), selected = ref<string[]>([])
const loading = ref(false), error = ref<ErrorValue>('')
let epoch = 0, controller: AbortController | undefined
async function load() {
  controller?.abort(); const request = controller = new AbortController(), token = ++epoch
  loading.value = true; error.value = ''; selected.value = []
  try { const result = await registrationDemo.documentHistory(props.kind, { ...query, documentId: props.documentId }, request.signal, props.documentModule); if (token === epoch) data.value = result }
  catch (issue) { if (token === epoch && !request.signal.aborted) { error.value = normalizeError(issue); data.value.items = [] } }
  finally { if (token === epoch) loading.value = false }
}
function search() { Object.assign(query, draft, { page: 1 }); void load() }
void load(); onBeforeUnmount(() => { epoch++; controller?.abort() })
</script>
<template>
  <BootstrapModal open :title="title" size="xl" scrollable @close="emit('close')">
    <form :aria-label="`${title}查询`" class="mb-3" @submit.prevent="search">
      <div class="row g-3 align-items-center">
        <div class="col-12 col-md"><div class="d-flex align-items-center gap-2"><label for="document-history-category" class="col-form-label text-nowrap">文件类型</label><input id="document-history-category" v-model="draft.category" class="form-control" maxlength="200" /></div></div>
        <div class="col-12 col-md"><div class="d-flex align-items-center gap-2"><label for="document-history-name" class="col-form-label text-nowrap">文件名称</label><input id="document-history-name" v-model="draft.name" class="form-control" maxlength="200" /></div></div>
        <div class="col-12 col-md-auto"><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading">查询</button></div>
      </div>
    </form>
    <DataTable :label="title" :rows="data.items" :columns="movementColumns" :row-key="row => row.id" :row-label="row => row.name" v-model:selected="selected" :loading="loading" :error="error" preserve-rows-on-loading :pagination="{ ...data, sizes: [10, 20, 50] }" @retry="load" @page="query.page = $event; load()" @size="query.pageSize = $event; query.page = 1; load()" />
    <template #footer><button type="button" class="btn btn-light" @click="emit('close')">返回</button></template>
  </BootstrapModal>
</template>
