<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import FileUploadStatus from '../common/FileUploadStatus.vue'
import { useFileUpload } from '../common/useFileUpload'
import TemplateToast from '../common/TemplateToast.vue'
import type { SampleTrademarkImage } from '../../types/commissions/sampleForm'
const props = defineProps<{ modelValue: SampleTrademarkImage | null; readonly?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [SampleTrademarkImage | null]; pending: [boolean] }>()
const fileInput = ref<HTMLInputElement>(), toast = ref<InstanceType<typeof TemplateToast>>(), message = ref(''), busy = ref(false)
const uploadStatus = useFileUpload()
let sequence = 0
async function upload(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  input.value = ''
  if (!file || props.readonly || busy.value) return
  const token = ++sequence; busy.value = true; uploadStatus.start(file.name); emit('pending', true)
  try {
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 2 * 1024 * 1024 || file.name.length > 200) throw new Error('请选择不超过 2 MB 的 PNG、JPEG 或 WebP 图片。')
    const dataUrl = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(new Error('图片读取失败，请重试。')); reader.readAsDataURL(file) })
    await new Promise<void>((resolve, reject) => { const image = new Image(); image.onload = () => resolve(); image.onerror = () => reject(new Error('图片无法读取，请重新选择。')); image.src = dataUrl })
    if (token === sequence) emit('update:modelValue', { name: file.name, dataUrl })
  } catch (error) { if (token === sequence) { message.value = error instanceof Error ? error.message : '图片上传失败。'; toast.value?.show() } }
  finally { if (token === sequence) { busy.value = false; uploadStatus.finish(); emit('pending', false) } }
}
onBeforeUnmount(() => { sequence++; emit('pending', false) })
</script>
<template>
  <div class="d-flex flex-wrap align-items-center gap-2 mt-2">
    <template v-if="modelValue"><img :src="modelValue.dataUrl" alt="商标图片" class="img-thumbnail avatar-lg object-fit-contain" /><a :href="modelValue.dataUrl" :download="modelValue.name" class="text-break">{{ modelValue.name }}</a></template>
    <template v-if="!readonly"><input ref="fileInput" class="d-none" type="file" accept="image/png,image/jpeg,image/webp" aria-label="上传商标图片" @change="upload" /><button type="button" class="btn btn-light btn-sm" :disabled="busy" @click="fileInput?.click()"><i class="ti ti-upload me-1" aria-hidden="true"></i>{{ busy ? '正在读取…' : modelValue ? '更换图片' : '上传图片' }}</button><button v-if="modelValue" type="button" class="btn btn-light btn-sm" aria-label="删除商标图片" :disabled="busy" @click="emit('update:modelValue', null)"><i class="ti ti-trash" aria-hidden="true"></i></button></template>
  </div>
  <FileUploadStatus :state="uploadStatus.state.value" :leave-attempted="uploadStatus.leaveAttempted.value" />
  <TemplateToast ref="toast" :message="message" tone="danger" />
</template>

