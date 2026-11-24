<template>
  <el-dialog v-model="open" title="子项目信息配置" width="1000px" append-to-body>
    <el-alert type="info" :closable="false" title="配置用于样品登记选择。停用只影响新选择，不改写历史样品；金额和付款信息在每份样品中填写。" />
    <div class="toolbar d-flex flex-wrap gap-2 mb-3">
      <el-button type="primary" @click="start()">新增子项目</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
      <el-input v-model="search" clearable placeholder="搜索编号、名称、部门" />
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table :data="filtered" border max-height="330" v-loading="loading" row-key="id">
      <el-table-column prop="code" label="编号" width="120" />
      <el-table-column prop="name" label="子项目名称" min-width="240" />
      <el-table-column prop="dept" label="核算部门" min-width="180" />
      <el-table-column prop="businessCategory" label="业务三级分类" min-width="180" />
      <el-table-column label="状态" width="80"><template #default="{ row }">{{ row.enabled ? '启用' : '停用' }}</template></el-table-column>
      <el-table-column label="操作" width="80"><template #default="{ row }"><el-button link @click="start(row)">修改</el-button></template></el-table-column>
    </el-table>
    <el-form v-if="draft" label-width="120px"  @submit.prevent="save">
      <el-form-item label="子项目编号"><el-input v-model="draft.code" maxlength="60" /></el-form-item>
      <el-form-item label="子项目名称"><el-input v-model="draft.name" maxlength="240" /></el-form-item>
      <el-form-item label="核算部门"><el-input v-model="draft.dept" maxlength="240" /></el-form-item>
      <el-form-item label="业务三级分类"><el-input v-model="draft.businessCategory" maxlength="160" /></el-form-item>
      <el-form-item label="启用"><el-switch v-model="draft.enabled" /></el-form-item>
      <el-form-item><el-button type="primary" :loading="saving" @click="save">保存配置</el-button><el-button @click="draft = null">取消编辑</el-button></el-form-item>
    </el-form>
  </el-dialog>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchSubprojects, saveSubproject, type SubprojectOption } from '@/services/businessSupplement'
const open = defineModel<boolean>({ default: false })
const emit = defineEmits<{ saved: [] }>()
const rows = ref<SubprojectOption[]>([])
const draft = ref<Partial<SubprojectOption> | null>(null)
const loading = ref(false), saving = ref(false), error = ref(''), search = ref('')
const filtered = computed(() => rows.value.filter(row => [row.code, row.name, row.dept, row.businessCategory].join(' ').includes(search.value.trim())))
function start(row?: SubprojectOption) { draft.value = row ? { ...row } : { code: '', name: '', dept: '', businessCategory: '', enabled: true } }
async function load() {
  loading.value = true; error.value = ''
  try { rows.value = await fetchSubprojects(true) }
  catch (e) { error.value = e instanceof Error ? e.message : '配置加载失败' }
  finally { loading.value = false }
}
async function save() {
  if (!draft.value || saving.value) return
  saving.value = true
  try { await saveSubproject(draft.value); draft.value = null; ElMessage.success('配置已保存'); emit('saved'); await load() }
  catch (e) { ElMessage.error(e instanceof Error ? e.message : '保存失败') }
  finally { saving.value = false }
}
watch(open, value => { if (value) { draft.value = null; void load() } })
</script>

