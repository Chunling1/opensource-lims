import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchReportDetail, type ReportDetailView } from '@/services/reports'
import type { DetailSection } from '@/components/DetailViewDialog.vue'

// 统一的"点击查看完整信息"只读弹窗：报告/样品按报告号拉取完整 detail.summary；委托/合同直接传 sections。
export function useDetailView() {
  const detailOpen = ref(false)
  const detailTitle = ref('')
  const detailSections = ref<DetailSection[]>([])
  const detailLoading = ref(false)
  const detailError = ref('')
  let lastRequest: { reportNo: string; view: ReportDetailView; title?: string } | null = null

  async function viewReportDetail(reportNo: string, view: ReportDetailView, title?: string) {
    lastRequest = { reportNo, view, title }
    detailTitle.value = title || `详情 · ${reportNo}`
    detailSections.value = []
    detailError.value = ''
    detailLoading.value = true
    detailOpen.value = true
    try {
      const d = await fetchReportDetail(reportNo, view)
      detailSections.value = d?.summary ?? []
    } catch (e) {
      detailError.value = e instanceof Error ? e.message : '加载详情失败'
      ElMessage.error(detailError.value)
    } finally {
      detailLoading.value = false
    }
  }

  function viewSections(title: string, sections: DetailSection[]) {
    lastRequest = null
    detailTitle.value = title
    detailSections.value = sections
    detailLoading.value = false
    detailError.value = ''
    detailOpen.value = true
  }

  function retryDetail() {
    if (lastRequest) void viewReportDetail(lastRequest.reportNo, lastRequest.view, lastRequest.title)
  }

  return {
    detailOpen, detailTitle, detailSections, detailLoading, detailError,
    viewReportDetail, viewSections, retryDetail,
  }
}
