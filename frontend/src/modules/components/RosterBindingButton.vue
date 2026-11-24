<template>
  <el-button v-if="!disabled" :loading="busy" @click="bind">使用名册手机号绑定</el-button>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { previewRosterBinding, bindRosterPhone } from '@/services/businessSupplement'
const props = withDefaults(defineProps<{ userId?: number | 'me'; disabled?: boolean }>(), { userId: 'me', disabled: false })
const emit = defineEmits<{ bound: [] }>()
const busy = ref(false)
async function bind() {
  if (busy.value || props.disabled) return
  busy.value = true
  try {
    const preview = await previewRosterBinding(props.userId)
    if (!preview.canBind) { ElMessage.info(preview.reason || '已有绑定，未修改'); emit('bound'); return }
    await ElMessageBox.confirm(
      '确认使用 ' + preview.legalName + ' 的名册手机号 ' + preview.mobileMasked + '？只建立本地签署绑定，不发送短信，也不代替本人实名或签字。',
      '确认签署身份', { confirmButtonText: '确认绑定', cancelButtonText: '取消', type: 'warning' })
    await bindRosterPhone(props.userId)
    ElMessage.success('已绑定，实名和签署仍由本人完成')
    emit('bound')
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error(e instanceof Error ? e.message : '绑定失败')
  } finally { busy.value = false }
}
</script>
