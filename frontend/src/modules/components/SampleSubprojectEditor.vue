<template>
  <section  :inert="disabled || undefined">
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
      <h4 class="h5 mb-3">子项目信息</h4>
      <el-button v-if="(session.fullPlatformAuthority || session.roleKey === 'admin') && !disabled" size="small" @click="catalogOpen = true">配置子项目</el-button>
      <el-button size="small" :loading="catalogLoading" @click="loadCatalog">刷新选项</el-button>
      <el-button size="small" @click="add">增加子项目</el-button>
    </div>
    <p v-if="internalContract" class="text-muted small">不回传外部ERP合同可不填写子项目；如填写，子项目金额合计须等于样品标准价格。</p>
    <el-alert v-if="catalogError" :title="catalogError" type="warning" :closable="false" />
    <el-alert v-if="erpError" :title="erpError" type="warning" :closable="false" />
    <p v-if="erpReceivedAt" class="text-muted small">外部ERP项目下发 · 接收时间 {{ erpReceivedAt }} · 选择后带入核算部门和业务分类，结算金额仍按本次样品填写。</p>
    <el-alert v-if="erpOptions.some(item => !item.dept || !item.businessCategory)" title="部分历史下发只包含部门、分类编码，未包含名称；缺失项不会按名称猜配，请核对外部ERP字典后补充。" type="warning" :closable="false" />
    <el-alert v-if="!internalContract && !catalogLoading && !catalog.length && !erpOptions.length && !erpError" type="info" :closable="false" :title="entrustNo ? '该委托关联的外部ERP项目暂无可选子项目；请核对下发信息。已有样品内容不会被覆盖。' : '请先选择委托单，以加载其外部ERP子项目。'" />
    <el-table :data="modelValue" border size="small" >
      <el-table-column label="子项目名称" min-width="230"><template #default="{ row, $index }">
        <el-select :model-value="selectedValue(row)" :disabled="disabled" :loading="catalogLoading" no-data-text="暂无该项目的可选子项目" escape-overflow filterable clearable placeholder="选择外部ERP下发子项目" @update:model-value="choose($index, $event)">
          <el-option v-for="item in erpOptions" :key="erpValue(item)" :label="(item.name || '待补子项目名称') + '（' + item.code + ' · 外部ERP' + (item.enabled ? '' : ' · ' + (item.sourceStatus || '不可选')) + '）'" :value="erpValue(item)" :disabled="!item.enabled" />
          <el-option v-for="item in catalog" :key="item.id" :label="(item.id === row.catalogId ? row.projectName : item.name) + '（' + item.code + '）'" :value="'catalog:' + item.id" />
          <el-option v-if="row.projectName && !hasOption(row)" :label="row.projectName + '（已保存快照）'" :value="selectedValue(row)" disabled />
        </el-select>
      </template></el-table-column>
      <el-table-column label="核算部门" min-width="190"><template #default="{ row, $index }">
        <el-select :model-value="row.dept" :disabled="row.source === 'erp'" escape-overflow filterable allow-create default-first-option clearable placeholder="选择或输入部门" @update:model-value="update($index, 'dept', $event)">
          <el-option v-for="name in departmentOptions" :key="name" :label="name" :value="name" />
        </el-select>
      </template></el-table-column>
      <el-table-column label="业务三级分类" min-width="190"><template #default="{ row, $index }">
        <el-select :model-value="row.businessCategory" :disabled="row.source === 'erp'" escape-overflow filterable allow-create default-first-option clearable placeholder="选择或输入分类" @update:model-value="update($index, 'businessCategory', $event)">
          <el-option v-for="name in categoryOptions" :key="name" :label="name" :value="name" />
        </el-select>
      </template></el-table-column>
      <el-table-column label="子项金额" min-width="130"><template #default="{ row, $index }"><el-input :model-value="row.amount" inputmode="decimal" placeholder="金额（元）" @update:model-value="update($index, 'amount', $event)" /></template></el-table-column>
      <el-table-column label="收款金额" min-width="130"><template #default="{ row, $index }"><el-input :model-value="row.receivedAmount" inputmode="decimal" placeholder="金额（元）" @update:model-value="update($index, 'receivedAmount', $event)" /></template></el-table-column>
      <el-table-column label="收款类型" min-width="130"><template #default="{ row, $index }">
        <el-select :model-value="row.receiptType" clearable placeholder="请选择" @update:model-value="update($index, 'receiptType', $event)">
          <el-option v-for="name in receiptOptions(row.receiptType)" :key="name" :label="name" :value="name" />
        </el-select>
      </template></el-table-column>
      <el-table-column label="付款说明（必填）" min-width="210"><template #default="{ row, $index }"><el-input :model-value="row.paymentDescription" type="textarea" placeholder="请填写付款说明" aria-required="true" :autosize="{ minRows: 1, maxRows: 4 }" @update:model-value="update($index, 'paymentDescription', $event)" /></template></el-table-column>
      <el-table-column label="备注" min-width="210"><template #default="{ row, $index }"><el-input :model-value="row.remark" type="textarea" :autosize="{ minRows: 1, maxRows: 4 }" @update:model-value="update($index, 'remark', $event)" /></template></el-table-column>
      <el-table-column label="操作" width="70" fixed="right"><template #default="{ $index }"><el-button size="small" text type="danger" @click="remove($index)">删除</el-button></template></el-table-column>
      <template #empty>暂无子项目</template>
    </el-table>
    <SubprojectCatalogDialog v-if="(session.fullPlatformAuthority || session.roleKey === 'admin') && !disabled" v-model="catalogOpen" @saved="loadCatalog" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useSessionStore } from '@/stores/session'
import SubprojectCatalogDialog from './SubprojectCatalogDialog.vue'
import { fetchSubprojects, fetchErpSubprojects, type SubprojectOption, type ErpSubprojectOption } from '@/services/businessSupplement'
import { blankSubproject, RECEIPT_TYPES, type SampleSubproject } from '@/composables/sampleSubprojects'
const props = withDefaults(defineProps<{ modelValue: SampleSubproject[]; entrustNo?: string; contractNo?: string; reportNo?: string; internalContract?: boolean; disabled?: boolean; departments?: string[]; projects?: string[]; categories?: string[] }>(), { entrustNo: '', disabled: false, departments: () => [], projects: () => [], categories: () => [] })
const emit = defineEmits<{ 'update:modelValue': [value: SampleSubproject[]] }>()
const unique = (values: string[]) => [...new Set(values.filter(Boolean))]
const catalog = ref<SubprojectOption[]>([])
const catalogError = ref('')
const session = useSessionStore()
const catalogLoading = ref(false), catalogOpen = ref(false)
const erpOptions = ref<ErpSubprojectOption[]>([]), erpError = ref(''), erpReceivedAt = ref('')
let loadGeneration = 0
async function loadCatalog() {
  const generation = ++loadGeneration
  catalogLoading.value = true; catalogError.value = ''
  erpOptions.value = []; erpError.value = ''; erpReceivedAt.value = ''
  const no = props.entrustNo
  await Promise.all([
    fetchSubprojects().then(rows => { if (generation === loadGeneration) catalog.value = rows })
      .catch(() => { if (generation === loadGeneration) { catalog.value = []; catalogError.value = '补充配置加载失败，已保存内容未改动。' } }),
    no && !props.internalContract ? fetchErpSubprojects(no, props.contractNo, props.reportNo).then(data => {
      if (generation === loadGeneration) { erpOptions.value = data.rows; erpReceivedAt.value = data.receivedAt }
    }).catch(() => { if (generation === loadGeneration) erpError.value = '外部ERP子项目读取失败，请核对委托关联及接收记录，点击刷新重试；已有内容保留。' }) : Promise.resolve(),
  ])
  if (generation === loadGeneration) catalogLoading.value = false
}
onMounted(loadCatalog)
watch(() => [props.entrustNo, props.contractNo, props.reportNo, props.internalContract], loadCatalog)
const erpValue = (item: ErpSubprojectOption) => 'erp:' + JSON.stringify([item.contractNo, item.code, item.sourceEventId])
const selectedValue = (row: SampleSubproject) => row.source === 'erp' ? 'erp:' + JSON.stringify([row.contractNo, row.catalogCode, row.sourceEventId]) : row.catalogId ? 'catalog:' + row.catalogId : row.projectName
const hasOption = (row: SampleSubproject) => row.source === 'erp'
  ? erpOptions.value.some(item => item.code === row.catalogCode && item.contractNo === row.contractNo && item.sourceEventId === row.sourceEventId)
  : catalog.value.some(item => item.id === row.catalogId)
function choose(index: number, value: string) {
  if (props.disabled) return
  const erp = erpOptions.value.find(item => erpValue(item) === value)
  if (erp) {
    if (!erp.enabled) return
    emit('update:modelValue', props.modelValue.map((row, i) => i !== index ? row : {
      ...row, source: 'erp', contractNo: erp.contractNo, catalogId: null,
      catalogCode: erp.code, catalogRevision: null, projectName: erp.name,
      dept: erp.dept, businessCategory: erp.businessCategory,
      sourceKey: erp.sourceKey, sourceEventId: erp.sourceEventId, sourceProof: erp.sourceProof,
    }))
    return
  }
  const selected = catalog.value.find(item => 'catalog:' + item.id === value)
  if (value && !selected) return
  emit('update:modelValue', props.modelValue.map((row, i) => i !== index ? row : {
    ...row, source: 'manual', sourceKey: '', sourceEventId: '', sourceProof: '', contractNo: '',
    catalogId: selected?.id ?? null, catalogCode: selected?.code ?? '',
    catalogRevision: selected?.revision ?? null, projectName: selected?.name ?? '',
    dept: selected?.dept ?? '', businessCategory: selected?.businessCategory ?? '',
  }))
}
const departmentOptions = computed(() => unique([...props.departments, ...props.modelValue.map(row => row.dept)]))
const categoryOptions = computed(() => unique([...props.categories, ...props.modelValue.map(row => row.businessCategory)]))
const receiptOptions = (current: string) => unique([...RECEIPT_TYPES, current])
function update(index: number, key: keyof SampleSubproject, value: string) {
  if (props.disabled) return
  if (props.modelValue[index]?.source === 'erp' && ['dept', 'businessCategory'].includes(String(key))) return
  emit('update:modelValue', props.modelValue.map((row, i) => i === index ? { ...row, ...(key === 'amount' && (!row.receivedAmount || Number(row.receivedAmount) === Number(row.amount)) ? {receivedAmount:value ?? ''} : {}), [key]: value ?? '' } : row))
}
function add() { if (!props.disabled) emit('update:modelValue', [...props.modelValue, blankSubproject()]) }
function remove(index: number) { if (!props.disabled) emit('update:modelValue', props.modelValue.filter((_, i) => i !== index)) }
</script>


