<template>
  <el-dialog
    :model-value="modelValue"
    title="CNAS / CMA 合规确认"
    width="760px"
    append-to-body
    :close-on-click-modal="false"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-alert
      v-if="preflight?.hardBlockers.length"
      type="error"
      :closable="false"
      show-icon
      title="存在不能确认绕过的问题，请退回修改后重新检查。"
    />
    <div v-if="preflight" >
      <span>委托要求：<b>{{ preflight.requestedSeal || '无' }}</b></span>
      <span>最终标识：<b>{{ preflight.finalSeal || '不使用 CNAS/CMA 标识' }}</b></span>
    </div>
    <el-empty v-if="!preflight" description="正在获取合规检查结果" />
    <div v-else >
      <div v-for="issue in preflight.issues" :key="issue.id"  :class="{ 'border-danger': issue.hardBlocker }">
        <el-checkbox
          v-if="issue.acknowledgeable"
          v-model="acknowledged"
          :value="issue.id"
        >
          <strong>{{ issue.title }}</strong>
        </el-checkbox>
        <strong v-else>{{ issue.title }}</strong>
        <p>{{ issue.message }}</p>
        <small v-if="issue.evidence?.standardCode || issue.evidence?.certificateNo">
          依据：{{ [issue.evidence.standardCode, issue.evidence.certificateNo].filter(Boolean).join(' · ') }}
        </small>
        <small v-if="issue.evidence?.objectName || issue.evidence?.itemName">
          对象/项目：{{ [issue.evidence.objectName, issue.evidence.itemName].filter(Boolean).join(' / ') }}
        </small>
        <small v-if="issue.effect">处理结果：{{ issue.effect }}</small>
        <small v-if="issue.evidence?.sourceFile">
          来源：{{ issue.evidence.sourceFile }} 第 {{ issue.evidence.sourcePage }} 页
        </small>
      </div>
      <el-alert
        v-if="!preflight.issues.length"
        type="success"
        :closable="false"
        show-icon
        title="当前未发现 CNAS/CMA 合规问题"
      />
    </div>
    <el-input
      v-if="preflight?.requiresOpinion"
      v-model="opinion"
      type="textarea"
      :rows="3"
      placeholder="填写本节点的合规确认意见（必填）"
    />
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button
        type="primary"
        :loading="loading"
        :disabled="!canConfirm"
        @click="confirm"
      >
        确认并继续
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { ComplianceConfirmation, CompliancePreflight } from '@/services/pipeline'

const props = defineProps<{
  modelValue: boolean
  preflight: CompliancePreflight | null
  loading?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: [payload: ComplianceConfirmation]
}>()
const acknowledged = ref<string[]>([])
const opinion = ref('')

watch(
  () => [props.modelValue, props.preflight?.preflightVersion],
  () => {
    acknowledged.value = []
    opinion.value = ''
  },
)

const acknowledgeableIds = computed(() => (
  props.preflight?.issues.filter((issue) => issue.acknowledgeable).map((issue) => issue.id) || []
))
const canConfirm = computed(() => (
  Boolean(props.preflight?.ready)
  && acknowledgeableIds.value.every((id) => acknowledged.value.includes(id))
  && (!props.preflight?.requiresOpinion || Boolean(opinion.value.trim()))
))

function confirm() {
  if (!props.preflight || !canConfirm.value) {
    ElMessage.warning('请逐项确认问题并填写确认意见')
    return
  }
  emit('confirm', {
    preflightVersion: props.preflight.preflightVersion,
    acknowledgedIssueIds: [...acknowledged.value],
    complianceOpinion: opinion.value.trim(),
    finalSeal: props.preflight.finalSeal,
  })
}
</script>


