<script setup lang="ts">
import { computed, ref } from 'vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { equipmentSchemes, type EquipmentScheme, type SchemeCatalogue } from './equipmentSchemes'
const props = defineProps<{ catalogue: SchemeCatalogue; scheme?: EquipmentScheme; initialIds?: string[] }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const name = ref(props.scheme?.name || ''), enabled = ref(props.scheme?.enabled ?? true)
const ids = ref([...(props.scheme?.equipmentIds || (props.initialIds || []).map(Number))])
const projects = ref([...(props.scheme?.projectIds || (props.catalogue.projectId ? [props.catalogue.projectId] : []))])
const keyword = ref(''), busy = ref(false), error = ref<ErrorValue>('')
const rows = computed(() => props.catalogue.equipment.filter(row => `${row.archiveNo} ${row.name} ${row.factoryNo || ''}`.toLowerCase().includes(keyword.value.trim().toLowerCase())))
const missing = computed(() => ids.value.filter(id => !props.catalogue.equipment.some(row => row.id === id)))
async function save() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    await equipmentSchemes.save({ id: props.scheme?.id, version: props.scheme?.version, departmentId: props.catalogue.departmentId,
      name: name.value.trim(), enabled: enabled.value, equipmentIds: ids.value, projectIds: projects.value })
    emit('saved')
  } catch (issue) { error.value = normalizeError(issue) }
  finally { busy.value = false }
}
</script>
<template>
  <BootstrapModal open :title="scheme ? '维护仪器方案' : '保存仪器方案'" size="xl" scrollable :busy="busy" @close="emit('close')">
    <ErrorNotice :error="error" />
    <fieldset :disabled="busy">
      <div class="row g-3 mb-3">
        <div class="col-md-8"><label for="instrument-scheme-name" class="form-label">方案名称（{{ catalogue.department }}）</label><input id="instrument-scheme-name" v-model="name" class="form-control" maxlength="100" required /></div>
        <div class="col-md-4 d-flex align-items-end"><label class="form-check mb-2"><input v-model="enabled" type="checkbox" class="form-check-input" />启用方案</label></div>
      </div>
      <details class="mb-3"><summary>关联检测项目（已选 {{ projects.length }} 项）</summary><p class="text-muted mt-2">关联后，填写该项目报告时优先推荐此方案；套用前仍逐台核对仪器。</p><div class="row g-2"><label v-for="project in catalogue.projects" :key="project.id" class="col-md-6"><input v-model="projects" type="checkbox" :value="project.id" class="form-check-input me-2" />{{ project.code }} {{ project.name }}</label></div></details>
      <label for="scheme-equipment-search" class="form-label">选择方案仪器（已选 {{ ids.length }} 台）</label>
      <input id="scheme-equipment-search" v-model="keyword" class="form-control mb-2" placeholder="按档案号、设备名称、出厂号筛选" />
      <p class="text-muted">保存组合不代表仪器可用于检测。每次套用按当时的台账、授权和试验日期核对；停用或校准不覆盖的仪器会跳过。</p>
      <div v-if="missing.length" class="alert alert-warning"><p>以下仪器已删除或不在当前授权范围，套用时不会带入；可在此移除：</p><label v-for="id in missing" :key="id" class="d-block"><input v-model="ids" type="checkbox" :value="id" class="form-check-input me-2" />仪器 ID {{ id }}</label></div>
      <div class="table-responsive"><table class="table table-striped table-hover table-nowrap align-middle"><thead><tr><th>选择</th><th>档案号</th><th>设备名称</th><th>所属部门</th><th>状态</th><th>校准日期</th><th>有效期至</th></tr></thead><tbody><tr v-for="row in rows" :key="row.id"><td><input v-model="ids" type="checkbox" :value="row.id" class="form-check-input" :aria-label="`方案仪器 ${row.archiveNo} ${row.name}`" /></td><td>{{ row.archiveNo }}</td><td>{{ row.name }}</td><td>{{ row.dept }}</td><td>{{ row.status }}</td><td>{{ row.actualCalDate || row.lastCalDate || '未登记' }}</td><td>{{ row.validUntil || row.planCalDate || '未登记' }}</td></tr><tr v-if="!rows.length"><td colspan="7" class="text-muted text-center">没有匹配的仪器</td></tr></tbody></table></div>
    </fieldset>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button><button type="button" class="btn btn-primary" :disabled="busy || !name.trim() || !ids.length" @click="save">{{ busy ? '正在保存…' : '保存方案' }}</button></template>
  </BootstrapModal>
</template>
