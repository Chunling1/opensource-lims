<script setup lang="ts">
import { ref, watch } from 'vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import RegistrationTestPlanBranch from './RegistrationTestPlanBranch.vue'
import { currentActor } from '../../stores/session'
import type { TestPlanNode } from '../../types/commissions/sampleForm'

const props = defineProps<{ open: boolean; valueId?: string; value?: string; valueCode?: string }>()
const emit = defineEmits<{ close: []; select: [TestPlanNode] }>()
const keyword = ref(''), applied = ref(''), queryVersion = ref(0), expanded = ref(true)
const selected = ref<TestPlanNode>()
function search() { applied.value = keyword.value.trim(); expanded.value = true; queryVersion.value++ }
watch(() => props.open, open => {
  selected.value = undefined
  if (open) {
    keyword.value = ''; applied.value = ''; expanded.value = true; queryVersion.value++
    if (props.valueId && props.value) selected.value = { id: props.valueId, name: props.value, kind: 'plan', code: props.valueCode || '', groupName: '' }
  }
})
watch(currentActor, () => { selected.value = undefined; emit('close') })
</script>

<template>
  <BootstrapModal :open="open" title="选择检测方案" size="lg" scrollable fullscreen-mobile fill-height body-class="px-3 pt-0 overflow-auto" @close="emit('close')">
    <template #toolbar>
      <form class="row g-2 align-items-center px-3 mb-3" aria-label="检测方案查询" @submit.prevent="search">
        <div class="col-12 col-sm-auto"><label for="test-plan-keyword" class="col-form-label">检测项目名称</label></div>
        <div class="col-12 col-sm"><input id="test-plan-keyword" v-model="keyword" class="form-control" maxlength="200" /></div>
        <div class="col-auto d-flex gap-1"><button class="btn btn-primary" type="submit">查询</button></div>
      </form>
    </template>
    <template v-if="open">
      <button v-if="!applied" type="button" class="btn text-start d-flex align-items-center gap-2 mb-2" :aria-expanded="expanded" aria-controls="test-plan-catalogue" @click="expanded = !expanded"><i :class="expanded ? 'ti ti-chevron-down' : 'ti ti-chevron-right'" aria-hidden="true"></i><i :class="expanded ? 'ti ti-folder-open' : 'ti ti-folder'" class="text-warning fs-3 flex-shrink-0" aria-hidden="true"></i>所有项目</button>
      <div v-show="expanded" id="test-plan-catalogue" :class="{ 'ms-3': !applied }">
        <RegistrationTestPlanBranch :key="queryVersion" :keyword="applied" :selected-id="selected?.id" @select="selected = $event" />
      </div>
    </template>
    <template #footer>
      <span v-if="selected" class="me-auto text-muted text-break">{{ selected.name }}</span>
      <button class="btn btn-light" type="button" @click="emit('close')">取消</button>
      <button class="btn btn-primary" type="button" :disabled="!selected" @click="selected && emit('select', selected)">确定</button>
    </template>
  </BootstrapModal>
</template>
