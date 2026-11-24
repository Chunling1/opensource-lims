import type { RouteRecordRaw } from 'vue-router'
import { managementGroups } from '../navigation/managementNavigation'
import { flattenNavigation } from '../navigation/navigation'
export const managementRoutes: RouteRecordRaw[] = [
  { path: '/inspection/quality/erp_content', component: () => import('../../views/quality/ErpContentView.vue'), meta: { title: '外部ERP内容管理' } },
  { path: '/quality/standards/categories', redirect: '/quality/standards/groups' },
  ...managementGroups.flatMap(group => [
    { path: `/${group.id}`, redirect: flattenNavigation(group.children)[0]!.to },
    ...flattenNavigation(group.children, true).map(page => page.children ? {
      path: page.to, redirect: flattenNavigation(page.children)[0]!.to,
    } : {
      path: page.to,
      component: ['/quality/personnel/registration', '/quality/personnel/query'].includes(page.to) ? () => import('../../views/quality/PersonnelRegistrationView.vue')
                    : page.to === '/customers/projects' ? () => import('../../views/customers/CustomerProjectsView.vue')
                    : page.to === '/customers/accounts' ? () => import('../../views/customers/CustomerAccountsView.vue')
        : ['/quality/requests', '/quality/approvals'].includes(page.to) ? () => import('../../views/quality/DailyRequestsView.vue')
        : page.to === '/quality/environment' ? () => import('../../views/quality/TestEnvironmentsView.vue')
        : page.to === '/quality/personnel/certificates' ? () => import('../../views/quality/PersonnelCertificatesView.vue')
        : page.to === '/quality/equipment/loan-records' ? () => import('../../views/quality/EquipmentLoanRecordsView.vue')
        : page.to === '/quality/equipment/reference-materials' ? () => import('../../views/quality/ReferenceMaterialsView.vue')
        : page.to === '/quality/equipment/suppliers' ? () => import('../../views/quality/EquipmentSuppliersView.vue')
        : page.to === '/quality/equipment/loans' ? () => import('../../views/quality/EquipmentLoansView.vue')
        : ['/quality/documents/library', '/quality/documents/monitoring'].includes(page.to) ? () => import('../../views/quality/DocumentLibraryView.vue')
        : page.to === '/quality/equipment/maintenance-costs' ? () => import('../../views/quality/MaintenanceCostsView.vue')
        : page.to === '/quality/equipment/consumables' ? () => import('../../views/quality/ConsumablesView.vue')
        : ['/quality/standards/library', '/quality/standards/department-library'].includes(page.to) ? () => import('../../views/quality/StandardsLibraryView.vue')
        : page.to === '/quality/equipment/types' ? () => import('../../views/quality/EquipmentTypesView.vue')
        : ['/quality/equipment/groups', '/quality/standards/groups'].includes(page.to) ? () => import('../../views/quality/EquipmentGroupDefinitionsView.vue')
        : page.to === '/quality/equipment/plans/overall' ? () => import('../../views/quality/EquipmentOverallPlanView.vue')
        : page.to === '/quality/equipment/plans/interim' ? () => import('../../views/quality/EquipmentInterimPlanView.vue')
        : page.to === '/quality/equipment/plans/calibration' ? () => import('../../views/quality/EquipmentCalibrationPlanView.vue')
        : ['/quality/equipment/monthly-calibration', '/quality/equipment/department-monthly-calibration'].includes(page.to) ? () => import('../../views/quality/MonthlyCalibrationView.vue')
        : ['/quality/equipment/ledger', '/quality/equipment/department-ledger'].includes(page.to) ? () => import('../../views/quality/EquipmentLedgerView.vue')
        : () => import('../../views/workspace/MenuPage.vue'),
      props: page.to === '/quality/approvals' ? { approvalMode: true } : page.to === '/quality/standards/groups' ? { definitionModule: 'standards' } : page.to === '/quality/documents/monitoring' ? { documentModule: 'monitoring' } : page.to === '/quality/personnel/query' ? { queryMode: true } : ['/quality/equipment/department-ledger', '/quality/equipment/department-monthly-calibration', '/quality/standards/department-library'].includes(page.to) ? { departmentMode: true } : undefined,
      meta: { title: page.label, permissionModule: page.module },
    }),
  ]),
]
