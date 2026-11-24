<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="860px"
    top="6vh"
    
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div >
      <div v-if="loading"  aria-live="polite">
        <el-skeleton :rows="7" animated />
        <span>正在加载完整信息…</span>
      </div>
      <el-result v-else-if="error" icon="error" title="完整信息加载失败" :sub-title="error">
        <template #extra><el-button type="primary" @click="$emit('retry')">重试</el-button></template>
      </el-result>
      <el-alert
        v-if="!loading && !error && sections.length"
        type="info"
        :closable="false"
        show-icon
        
        title="只读查看"
      />
      <el-form v-if="!loading && !error && sections.length" disabled label-position="top" >
        <section v-for="sec in sections" :key="sec.title" class="mb-4">
          <h4 class="h5 mb-3">{{ sec.title }}</h4>
          <div class="row g-3">
            <el-form-item
              v-for="[label, value] in sec.fields"
              :key="label"
              :label="label"
              class="col-12 col-md-6"
              :class="{ 'col-md-12': isWide(value) }"
            >
              <el-input
                :model-value="value || '—'"
                :type="isWide(value) ? 'textarea' : 'text'"
                :autosize="isWide(value) ? { minRows: 2, maxRows: 6 } : undefined"
              />
            </el-form-item>
          </div>
        </section>
      </el-form>
      <el-empty v-if="!loading && !error && !sections.length" description="暂无可展示的信息" :image-size="60" />
    </div>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
export type DetailSection = { title: string; fields: [string, string][] }
defineProps<{ modelValue: boolean; title: string; sections: DetailSection[]; loading?: boolean; error?: string }>()
defineEmits<{ 'update:modelValue': [boolean]; retry: [] }>()
// 长文本（备注/地址等）整行展示
function isWide(v: string) {
  return typeof v === 'string' && (v.length > 24 || v.includes('；') || v.includes('\n'))
}
</script>


