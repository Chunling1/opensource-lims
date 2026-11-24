import type { RouteRecordRaw } from 'vue-router'
import { modules } from '@/data/modules'
const DashboardPage=()=>import('../../views/workspace/DashboardView.vue')
const StandardPage=()=>import('@/pages/StandardPage.vue')
const ReportPage=()=>import('@/pages/ReportPage.vue')
const PortalPage=()=>import('@/pages/PortalPage.vue')
const ApprovalPage=()=>import('@/pages/ApprovalPage.vue')
const CapabilityPage=()=>import('@/pages/CapabilityPage.vue')
const OrgPage=()=>import('@/pages/OrgPage.vue')
const ContractReviewPage=()=>import('@/pages/ContractReviewPage.vue')
const SampleInboundPage=()=>import('@/pages/SampleInboundPage.vue')
const SampleRegisterPage=()=>import('@/pages/SampleRegisterPage.vue')
const SampleOutboundPage=()=>import('@/pages/SampleOutboundPage.vue')
const EntrustChangePage=()=>import('@/pages/EntrustChangePage.vue')
const ChangeFormPage=()=>import('@/pages/ChangeFormPage.vue')
const ReportDataEntryPage=()=>import('@/pages/ReportDataEntryPage.vue')
const StdLibraryPage=()=>import('@/pages/StdLibraryPage.vue')
const EquipmentLedgerPage=()=>import('@/pages/EquipmentLedgerPage.vue')
const PersonnelPage=()=>import('@/pages/PersonnelPage.vue')
const ProjectConfigPage=()=>import('@/pages/ProjectConfigPage.vue')
const ElnGatewayPage=()=>import('@/pages/ElnGatewayPage.vue')
const BimCadLabPage=()=>import('@/pages/BimCadLabPage.vue')
const EsignCenterPage=()=>import('@/pages/EsignCenterPage.vue')
const EsignSettingsView=()=>import('../../views/system/EsignSettingsView.vue')
const TemplateMappingView=()=>import('../../views/system/TemplateMappingView.vue')
const pageComponents = {
  dashboard: DashboardPage,
  standard: StandardPage,
  report: ReportPage,
  contract_review: ContractReviewPage,
  sample_inbound: SampleInboundPage,
  sample_register: SampleRegisterPage,
  sample_outbound: SampleOutboundPage,
  entrust_change: EntrustChangePage,
  change_form: ChangeFormPage,
  data_entry: ReportDataEntryPage,
  std_library: StdLibraryPage,
  equipment_ledger: EquipmentLedgerPage,
  personnel: PersonnelPage,
  project_config: ProjectConfigPage,
  eln_gateway: ElnGatewayPage,
  bim_cad_lab: BimCadLabPage,
  esign: EsignCenterPage,
  esign_settings: EsignSettingsView,
  template_mapping: TemplateMappingView,
  portal: PortalPage,
  approval: ApprovalPage,
  integration: CapabilityPage,
  template: CapabilityPage,
  collection: CapabilityPage,
  notification: CapabilityPage,
  auth: OrgPage,
  org: OrgPage,
}
export const originalPlatformRoutes: RouteRecordRaw[] = modules.flatMap(module=>module.pages.map(page=>({path:page.path,component:pageComponents[page.type],meta:{title:page.name,moduleKey:module.key,moduleName:module.name,area:module.area,areaName:module.areaName,pageKey:page.key,pageName:page.name,pageType:page.type,permission:page.permission,modulePermission:module.permission,originalPlatform:true}})))
for (const module of modules) if (!module.pages.some(page=>page.path===module.path)) originalPlatformRoutes.push({path:module.path,redirect:module.pages[0]!.path})
originalPlatformRoutes.push({path:'/inspection/report/report_check',redirect:{path:'/platform-availability',query:{destination:'/reports/check'}}},{path:'/inspection/system/user',redirect:'/inspection/system/org'})
