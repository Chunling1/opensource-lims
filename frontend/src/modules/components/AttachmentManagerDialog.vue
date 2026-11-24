<template>
  <el-dialog :model-value="modelValue" :title="title" width="980px" append-to-body @open="load" @closed="close" @update:model-value="emit('update:modelValue', $event)">
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
      <span class="text-muted">{{ reportNo }}</span>
      <el-upload :auto-upload="false" :show-file-list="false" :on-change="uploadChanged" multiple>
        <el-button type="primary" :icon="Upload" :loading="uploading">上传附件</el-button>
      </el-upload>
    </div>
    <div class="row g-3">
      <el-table :data="rows" border height="430" highlight-current-row @row-click="preview">
        <el-table-column prop="name" label="文件名" min-width="260" show-overflow-tooltip />
        <el-table-column prop="type" label="类型" width="90" />
        <el-table-column prop="source" label="来源" min-width="140" />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :icon="View" @click.stop="preview(row)">预览</el-button>
            <el-button link :icon="Download" @click.stop="download(row)">下载</el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无附件" :image-size="60" /></template>
      </el-table>
      <div >
        <DataEntryPreview v-if="previewUrl && previewable" :url="previewUrl" :title="previewName" name="" type="" embedded compact persistent hide-download />
        <el-empty v-else :description="previewUrl ? '该格式请下载后查看' : '选择附件预览'" :image-size="60" />
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import DataEntryPreview from '../../components/testing/DataEntryPreview.vue'
import { onUnmounted, ref } from 'vue'
import { Download, Upload, View } from '@element-plus/icons-vue'
import { ElMessage, type UploadFile } from 'element-plus'
import { attachmentObjectUrl, isPreviewable, listUploadedAttachments, uploadAttachment, type Attachment } from '@/services/attachments'
import type { ReportDetailView } from '@/services/reports'

const props = withDefaults(defineProps<{ modelValue: boolean; reportNo: string; view: ReportDetailView; title?: string }>(), {
  title: '附件管理',
})
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const rows = ref<Attachment[]>([])
const uploading = ref(false)
const previewUrl = ref('')
const previewName = ref('')
const previewable = ref(false)

function revokePreview() {
  if (previewUrl.value.startsWith('blob:')) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
  previewName.value = ''
  previewable.value = false
}
async function load() {
  revokePreview()
  rows.value = props.reportNo ? await listUploadedAttachments(props.reportNo, props.view) : []
}
async function uploadChanged(file: UploadFile) {
  if (!file.raw || !props.reportNo) return
  uploading.value = true
  try {
    await uploadAttachment(props.reportNo, file.raw)
    await load()
    ElMessage.success('附件已上传')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '附件上传失败')
  } finally {
    uploading.value = false
  }
}
async function preview(row: Attachment) {
  revokePreview()
  const result = await attachmentObjectUrl(row, props.view)
  previewUrl.value = result.url
  previewName.value = row.name
  previewable.value = isPreviewable(result.contentType, row.name)
}
async function download(row: Attachment) {
  const result = await attachmentObjectUrl(row, props.view, true)
  const link = document.createElement('a')
  link.href = result.url
  link.download = row.name
  link.click()
  if (result.url.startsWith('blob:')) setTimeout(() => URL.revokeObjectURL(result.url), 1000)
}
function close() { revokePreview() }
onUnmounted(revokePreview)
</script>


