<template>
  <el-alert type="info" :closable="false" show-icon title="按具体菜单功能授权：页面内操作仍受项目编号、数据范围和流程状态限制。模块入口不等于全部子菜单权限。" />
  <AdaptiveTableActions class="mb-3" label="功能授权" :table-controls="false" :actions="permissionActions" @action="runPermissionAction" />
  <div v-for="section in displaySections" :key="section.key" class="mb-3">
    <p v-if="section.historical" class="text-muted mb-2">独立及历史功能</p>
    <div class="accordion">
      <div v-for="group in section.groups" :key="group.key" class="accordion-item">
        <h3 class="accordion-header">
          <button type="button" class="accordion-button gap-2" :class="{ collapsed: !expanded[section.key + group.key] }"
            :aria-expanded="!!expanded[section.key + group.key]" :aria-controls="panelId(section.key, group.key)"
            @click="toggleGroup(section.key + group.key)">
            {{ group.name }}
            <span class="badge bg-primary-subtle text-primary">已选 {{ selectedCount(group.codes) }} / {{ group.codes.length }}</span>
          </button>
        </h3>
        <div v-show="expanded[section.key + group.key]" :id="panelId(section.key, group.key)" class="accordion-body">
          <AdaptiveTableActions class="mb-3" :label="group.name" :table-controls="false" :actions="groupActions" @action="setSection(group.codes, $event === 0)" />
          <div class="row g-2">
            <div v-for="permission in group.items" :key="permission.code" class="col-12 col-md-6 col-xl-4">
              <button type="button" class="btn w-100 text-start d-flex align-items-center gap-2 h-100"
                :class="modelValue.includes(permission.code) ? 'btn-primary' : 'btn-outline-secondary'"
                :aria-pressed="modelValue.includes(permission.code)" :disabled="disabled"
                @click="setSection([permission.code], !modelValue.includes(permission.code))">
                <i :class="modelValue.includes(permission.code) ? 'ti ti-square-check' : 'ti ti-square'" aria-hidden="true"></i>
                {{ permission.name }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
// BEGIN TEMPLATE PERMISSIONS IMPORTS
import { ref, useId } from 'vue'
import AdaptiveTableActions from '../../components/common/table/AdaptiveTableActions.vue'
// END TEMPLATE PERMISSIONS IMPORTS

import { permissionMenuSections, setPermissionSection } from '@/data/permissionMenuSelection'

const props = withDefaults(defineProps<{
  modelValue: string[]
  permissions: { code: string; name: string; ptype: string }[]
  disabled?: boolean
}>(), { disabled: false })
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()
const sections = computed(() => permissionMenuSections(props.permissions))
const menuCodes = computed(() => sections.value.menus.flatMap((group) => group.codes))
const independentCodes = computed(() => sections.value.independent.flatMap((group) => group.codes))
const selectedCount = (codes: string[]) => codes.filter((code) => props.modelValue.includes(code)).length
function setSection(codes: string[], checked: boolean) {
  if (!props.disabled) emit('update:modelValue', setPermissionSection(props.modelValue, codes, checked))
}
function updateSelection(values: (string | number | boolean)[]) {
  if (!props.disabled) emit('update:modelValue', values.map(String))
}

// BEGIN TEMPLATE PERMISSIONS ADAPTER
const groupActions=computed(()=>[{label:'本组全选',icon:'ti ti-checks',disabled:props.disabled},{label:'清空',icon:'ti ti-square',disabled:props.disabled}])
const permissionActions=computed(()=>[{label:'全选菜单',icon:'ti ti-checks',disabled:props.disabled},{label:'清空菜单',icon:'ti ti-square',disabled:props.disabled}])
function runPermissionAction(index:number){setSection(menuCodes.value,index===0)}
const expanded = ref<Record<string, boolean>>({})
const instanceId = useId()
const panelId = (section: string, group: string) => `permissions-${instanceId}-${section}-${group}`
function toggleGroup(key: string) { expanded.value[key] = !expanded.value[key] }
const displaySections = computed(() => [
  { key: 'menus', historical: false, groups: sections.value.menus },
  { key: 'independent', historical: true, groups: sections.value.independent },
].filter(section => section.groups.length))
// END TEMPLATE PERMISSIONS ADAPTER
</script>


