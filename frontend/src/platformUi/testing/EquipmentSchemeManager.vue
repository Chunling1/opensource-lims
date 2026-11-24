<script setup lang="ts">
import { onMounted, ref } from 'vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import EquipmentSchemeEditor from './EquipmentSchemeEditor.vue'
import { equipmentSchemes, type EquipmentScheme, type SchemeCatalogue } from './equipmentSchemes'
const emit = defineEmits<{ close: [] }>()
const catalogue = ref<SchemeCatalogue>(), departmentId = ref<number>(), editing = ref<EquipmentScheme | 'new'>()
const busy = ref(false), error = ref<ErrorValue>('')
async function load() {
  busy.value = true; error.value = ''; catalogue.value = undefined
  try { catalogue.value = await equipmentSchemes.catalogue(undefined, departmentId.value); departmentId.value = catalogue.value.departmentId }
  catch (issue) { error.value = normalizeError(issue) }
  finally { busy.value = false }
}
async function saved() { editing.value = undefined; await load() }
onMounted(load)
</script>
<template>
  <BootstrapModal open title="部门仪器方案" size="xl" scrollable :busy="busy" @close="emit('close')">
    <ErrorNotice :error="error" />
    <p>保存常用仪器组合，并关联检测项目。录入时按本次试验日期逐台核对，只带入可用仪器。</p>
    <div class="d-flex flex-wrap gap-2 align-items-center mb-3">
      <label for="scheme-manager-department">所属部门</label><select id="scheme-manager-department" v-model="departmentId" class="form-select w-auto" :disabled="busy" @change="load"><option v-for="row in catalogue?.departments || []" :key="row.id" :value="row.id">{{ row.name }}</option></select>
      <button v-if="catalogue?.canManage" type="button" class="btn btn-primary" :disabled="busy" @click="editing = 'new'">新增仪器方案</button>
      <button type="button" class="btn btn-light" :disabled="busy" @click="load">刷新</button>
    </div>
    <div class="table-responsive"><table class="table table-striped table-nowrap align-middle"><thead><tr><th>方案名称</th><th>仪器数量</th><th>关联检测项目</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="row in catalogue?.schemes || []" :key="row.id"><td>{{ row.name }}</td><td>{{ row.equipmentIds.length }}</td><td>{{ row.projectIds.map(id => catalogue?.projects.find(p => p.id === id)?.code || `项目ID ${id}`).join('、') || '部门通用' }}</td><td>{{ row.enabled ? '启用' : '停用' }}</td><td><button v-if="catalogue?.canManage" type="button" class="btn btn-light btn-sm" :disabled="busy" @click="editing = row">维护</button></td></tr><tr v-if="catalogue && !catalogue.schemes.length"><td colspan="5" class="text-center text-muted">本部门暂无仪器方案，可新增常用组合。</td></tr></tbody></table></div>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">关闭</button></template>
  </BootstrapModal>
  <EquipmentSchemeEditor v-if="editing && catalogue" :catalogue="catalogue" :scheme="editing === 'new' ? undefined : editing" @close="editing = undefined" @saved="saved" />
</template>
