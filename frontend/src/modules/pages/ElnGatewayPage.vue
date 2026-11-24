<template>
  <ModuleWorkspace :title="pageName" :area-name="areaName" :module-name="moduleName" :path="route.path" :pages="pages" :active-key="pageKey" :show-command="false" :show-content="false">
  <section >
    <div >原</div>
    <div>
      <p >电子原始记录独立工作台</p>
      <h2 class="h5 mb-3">{{ pageName }}</h2>
      <p>{{ description }}</p>
      <ul>
        <li>每次打开都会重新校验账号、部门、功能权限和项目步骤授权。</li>
        <li>录入人与审核人必须是不同账号，审核通过后才形成正式 PDF。</li>
        <li>结构化结果只可人工确认写入检测数据当前表单，不会自动保存或推进流程。</li>
      </ul>
      <el-button type="primary" :loading="opening" @click="openWorkspace">打开电子原始记录工作台</el-button>
    </div>
  </section>
  </ModuleWorkspace>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { modules } from '@/data/modules'
import { createElnWorkspaceLaunch } from '@/services/eln'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'

const route = useRoute()
const opening = ref(false)
const pageName = computed(() => String(route.meta.pageName || '电子原始记录'))
const pageKey = computed(() => String(route.meta.pageKey || 'original_record_query'))
const areaName = computed(() => String(route.meta.areaName || ''))
const moduleName = computed(() => String(route.meta.moduleName || ''))
const pages = computed(() => modules.find(item => item.key === 'testing')?.pages || [])
const description = computed(() => ({
  original_record_query: '查询本人录入、审核或当前数据权限范围内的电子原始记录。',
  original_record_review: '处理明确分派给本人的交叉审核任务。',
  original_record_template: '按检测项目维护和发布原始记录模板，并逐项目启用。',
} as Record<string, string>)[pageKey.value] || '进入独立电子原始记录工作台。')

async function openWorkspace() {
  const target = window.open('', '_blank')
  opening.value = true
  try {
    const result = await createElnWorkspaceLaunch()
    if (target) target.location.replace(result.url)
    else ElMessage.warning('浏览器阻止了新窗口，请允许本站弹出窗口后重试')
  } catch (error) {
    target?.close()
    ElMessage.error(error instanceof Error ? error.message : '工作台入口创建失败')
  } finally {
    opening.value = false
  }
}
</script>


