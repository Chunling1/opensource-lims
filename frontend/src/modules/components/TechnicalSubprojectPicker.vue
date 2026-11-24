<template>
  <section><h4 class="h5 mb-3">检测子项目信息</h4><el-alert v-if="error || (!loading && !catalog.length)" :title="error || '暂无检测子项目配置，请管理员在项目配置示例建设立项目与参数/方法的关联。'" type="info" :closable="false" />
    <el-select :model-value="modelValue.map(r => r.id)" :disabled="disabled" multiple filterable :loading="loading" placeholder="按所属项目选择检测子项目" @update:model-value="choose"><el-option v-for="r in options" :key="r.id" :value="r.id" :label="`${r.projectName} / ${r.name}（${r.code}）`" /></el-select><el-button @click="load">刷新配置</el-button>
    <el-table :data="modelValue" border size="small"><el-table-column prop="name" label="子项目" /><el-table-column prop="department" label="所属部门" /><el-table-column prop="location" label="场所" /><el-table-column label="参数 / 方法 / 标准" min-width="260"><template #default="{ row }">{{ row.parameters.map((p: { name: string; method: string; standard: string }) => `${p.name} / ${p.method} / ${p.standard}`).join('；') }}</template></el-table-column><el-table-column prop="templateName" label="模板" /></el-table>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { listTechnicalSubprojects, type TechnicalSubproject } from '@/services/technicalSubprojects'
const props = defineProps<{ modelValue: TechnicalSubproject[]; disabled?: boolean }>(), emit = defineEmits<{ 'update:modelValue': [TechnicalSubproject[]] }>()
const catalog = ref<TechnicalSubproject[]>([]), loading = ref(false), error = ref('')
const options = computed(() => [...new Map([...catalog.value, ...props.modelValue].map(r => [r.id, r])).values()])
async function load() { loading.value = true; error.value = ''; try { catalog.value = await listTechnicalSubprojects() } catch (e) { error.value = e instanceof Error ? e.message : '读取失败' } finally { loading.value = false } }
function choose(ids: number[]) { if (props.disabled) return; const existing = new Map(props.modelValue.map(r => [r.id, r])); const selected = ids.map(id => existing.get(id) || catalog.value.find(r => r.id === id)).filter((r): r is TechnicalSubproject => !!r); emit('update:modelValue', JSON.parse(JSON.stringify(selected))) }
onMounted(load)
</script>
