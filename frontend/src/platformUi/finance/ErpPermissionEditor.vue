<script setup lang="ts">
import { computed } from 'vue'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import FinanceOperationSummary from './FinanceOperationSummary.vue'
import type { FormSchema } from '../../types/forms'
import { toggleErpRole } from './erpPermissions'
const props = defineProps<{ modelValue: string[]; administrator: boolean; canManage: boolean; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()
const options = [
  { code: 'view', name: '查看', description: '查看回传任务及结果' },
  { code: 'review', name: '核对', description: '核对和确认回传内容' },
  { code: 'send', name: '发送', description: '手动回传外部ERP；同时选中查看、核对' },
  { code: 'reverse', name: '反审核', description: '反审核已回传订单；同时选中其余三项' },
]
const notice = computed(() => props.administrator
  ? '管理员自动拥有全部外部ERP回传权限，无需单独勾选。'
  : props.canManage ? '按人员单独授权，随人员授权一起保存。授权后仍按数据范围、合同类型和流程状态校验，不会自动回传。'
  : '仅管理员可以调整外部ERP回传授权。')
const schema = computed<FormSchema<string[]>>(() => ({ sections: [{
  id: 'erp-personnel-grants', title: '外部ERP回传权限', fields: [{id:'erp-grant-help',label:'授权说明',labelHidden:true,control:'custom',slot:'instructions',width:'col-12'}, ...options.map(option => ({
    id: 'erp-grant-' + option.code, label: option.name, control: 'checkbox' as const,
    hint: option.description, width: 'col-12 col-sm-6',
    binding: { get: () => props.administrator || props.modelValue.includes(option.code),
      set: (_: string[], selected: boolean) => {
        if (props.administrator || !props.canManage || props.disabled) return
        emit('update:modelValue', toggleErpRole(props.modelValue, option.code, selected))
      } },
  }))],
}] }))
</script>
<template>
  <SchemaForm :schema="schema" :model="modelValue" :readonly="administrator || !canManage || disabled">
    <template #instructions><FinanceOperationSummary :text="notice" /></template>
  </SchemaForm>
</template>
