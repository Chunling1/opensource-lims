import { profile } from './auth'
const pages = new Set([
 '/inspection/entrust/agreement', '/inspection/entrust/registration', '/inspection/entrust/sample_register', '/inspection/entrust/query',
 '/inspection/testing/data_entry', '/inspection/testing/data_change', '/inspection/report/query',
 '/inspection/quality/personnel_registration', '/inspection/quality/equipment_ledger', '/inspection/quality/standard_library',
 '/inspection/quality/erp_content', '/inspection/system/custom_project',
])
export const correctionPage = (path: string) => !!profile.value?.features?.businessDataCorrection && pages.has(path)
