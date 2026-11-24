<template>
  <el-dialog v-model="open" title="检测子项目配置（参数 / 方法 / 标准 / 模板）" width="1100px" append-to-body>
    <el-alert title="这里配置检测子项目，不替代结算金额子项目。参数、方法和标准必须从现有能力库选择；配置不自动授予检测资质或人员权限。" type="info" :closable="false" />
    <el-button  @click="edit()">新增检测子项目</el-button>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table :data="rows" border max-height="230"><el-table-column prop="code" label="编号" /><el-table-column prop="name" label="名称" /><el-table-column prop="projectName" label="所属项目" /><el-table-column prop="location" label="场所" /><el-table-column label="状态"><template #default="{ row }">{{ row.enabled ? '启用' : '停用' }}</template></el-table-column><el-table-column label="操作"><template #default="{ row }"><el-button link @click="edit(row)">修改</el-button></template></el-table-column></el-table>
    <el-form v-if="draft" label-width="110px" >
      <el-form-item label="所属项目"><el-select v-model="draft.projectId" filterable placeholder="请选择项目"><el-option v-for="p in options.projects" :key="p.id" :value="p.id" :label="`${p.name}（${p.code}）`" /></el-select></el-form-item>
      <el-form-item label="子项目编号"><el-input v-model="draft.code" maxlength="60" /></el-form-item><el-form-item label="子项目名称"><el-input v-model="draft.name" maxlength="240" /></el-form-item>
      <el-form-item label="所属部门"><el-input v-model="draft.department" maxlength="240" /></el-form-item><el-form-item label="适用场所"><el-select v-model="draft.location" placeholder="选择参数所属地点"><el-option v-for="site in sites" :key="site" :value="site" :label="site" /></el-select></el-form-item>
      <el-form-item label="报告模板"><el-select v-model="draft.templateId" filterable><el-option v-for="t in options.templates" :key="t.id" :value="t.id" :label="`${t.name}（${t.code}）`" /></el-select></el-form-item>
      <el-form-item label="查找参数"><el-input v-model="keyword" placeholder="输入至少两个字：标准编号 / 参数名称" @keyup.enter="search" /><el-button :loading="searching" @click="search">搜索能力库</el-button></el-form-item>
      <el-form-item label="参数 / 方法"><el-select v-model="draft.parameterIds" multiple filterable placeholder="选择库内参数，不同场所请分建子项目"><el-option v-for="p in parameterOptions" :key="p.id" :value="p.id" :label="`${p.name} / ${p.standard} / ${p.method || '未填写方法条款'} / ${p.site}`" /></el-select></el-form-item>
      <el-form-item label="启用"><el-switch v-model="draft.enabled" /></el-form-item><el-form-item><el-button type="primary" :loading="saving" @click="save">保存配置</el-button><el-button @click="draft = null">取消</el-button></el-form-item>
    </el-form>
  </el-dialog>
</template>
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { listTechnicalSubprojects, technicalOptions, saveTechnicalSubproject, type TechnicalSubproject, type TechnicalOptions } from '@/services/technicalSubprojects'
const open = defineModel<boolean>({ default: false }), emit = defineEmits<{ saved: [] }>()
const rows = ref<TechnicalSubproject[]>([]), options = ref<TechnicalOptions>({ projects: [], templates: [], parameters: [] }), draft = ref<(Partial<TechnicalSubproject> & { parameterIds: number[] }) | null>(null)
const error = ref(''), saving = ref(false), searching = ref(false), keyword = ref('')
const parameterOptions = computed(() => [...new Map([...(draft.value?.parameters || []), ...options.value.parameters].map(p => [p.id, p])).values()])
const sites = computed(() => [...new Set(parameterOptions.value.filter(p => draft.value?.parameterIds.includes(p.id)).map(p => p.site))])
function edit(row?: TechnicalSubproject) { draft.value = row ? { ...JSON.parse(JSON.stringify(row)), parameterIds: row.parameters.map(p => p.id) } : { code: '', name: '', department: '', location: '', enabled: true, parameterIds: [] } }
async function load() { error.value = ''; try { const [r, o] = await Promise.all([listTechnicalSubprojects(true), technicalOptions()]); rows.value = r; options.value = o } catch (e) { error.value = e instanceof Error ? e.message : '配置加载失败' } }
async function search() { if (keyword.value.trim().length < 2) { error.value = '请输入至少两个字'; return } searching.value = true; try { options.value = await technicalOptions(keyword.value); error.value = '' } catch (e) { error.value = e instanceof Error ? e.message : '搜索失败' } finally { searching.value = false } }
async function save() { if (!draft.value || saving.value) return; saving.value = true; error.value = ''; try { await saveTechnicalSubproject(draft.value); draft.value = null; emit('saved'); await load() } catch (e) { error.value = e instanceof Error ? e.message : '保存失败' } finally { saving.value = false } }
watch(open, value => { if (value) { draft.value = null; void load() } })
</script>

