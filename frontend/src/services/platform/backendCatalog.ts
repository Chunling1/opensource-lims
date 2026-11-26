// Generated from the supplied platform backend Python route declarations.
// Static method/path evidence only; not a claim that all operations have been tested live.
export const backendCatalog = {
  "GET /api/ready": {
    "method": "GET",
    "path": "/api/ready"
  },
  "GET /api/health": {
    "method": "GET",
    "path": "/api/health"
  },
  "GET /api/admin/project-masters": {
    "method": "GET",
    "path": "/api/admin/project-masters"
  },
  "GET /api/admin/portal-service-catalog/diagnostics": {
    "method": "GET",
    "path": "/api/admin/portal-service-catalog/diagnostics"
  },
  "POST /api/admin/portal-service-catalog/sync": {
    "method": "POST",
    "path": "/api/admin/portal-service-catalog/sync"
  },
  "POST /api/admin/project-masters": {
    "method": "POST",
    "path": "/api/admin/project-masters"
  },
  "PUT /api/admin/project-masters/<int:project_id>": {
    "method": "PUT",
    "path": "/api/admin/project-masters/<int:project_id>"
  },
  "DELETE /api/admin/project-masters/<int:project_id>": {
    "method": "DELETE",
    "path": "/api/admin/project-masters/<int:project_id>"
  },
  "GET /api/admin/users": {
    "method": "GET",
    "path": "/api/admin/users"
  },
  "GET /api/admin/users/<int:uid>": {
    "method": "GET",
    "path": "/api/admin/users/<int:uid>"
  },
  "GET /api/admin/catalog": {
    "method": "GET",
    "path": "/api/admin/catalog"
  },
  "GET /api/admin/standard-catalog": {
    "method": "GET",
    "path": "/api/admin/standard-catalog"
  },
  "PUT /api/admin/users/<int:uid>": {
    "method": "PUT",
    "path": "/api/admin/users/<int:uid>"
  },
  "POST /api/admin/users": {
    "method": "POST",
    "path": "/api/admin/users"
  },
  "POST /api/admin/users/<int:uid>/reset-password": {
    "method": "POST",
    "path": "/api/admin/users/<int:uid>/reset-password"
  },
  "GET /api/admin/departments/tree": {
    "method": "GET",
    "path": "/api/admin/departments/tree"
  },
  "GET /api/admin/departments/<int:did>/members": {
    "method": "GET",
    "path": "/api/admin/departments/<int:did>/members"
  },
  "GET /api/admin/departments/<int:did>/authorizations": {
    "method": "GET",
    "path": "/api/admin/departments/<int:did>/authorizations"
  },
  "PUT /api/admin/departments/<int:did>/authorizations": {
    "method": "PUT",
    "path": "/api/admin/departments/<int:did>/authorizations"
  },
  "GET /api/admin/departments/<int:did>/members/<int:uid>/authorizations": {
    "method": "GET",
    "path": "/api/admin/departments/<int:did>/members/<int:uid>/authorizations"
  },
  "PUT /api/admin/departments/<int:did>/members/<int:uid>/authorizations": {
    "method": "PUT",
    "path": "/api/admin/departments/<int:did>/members/<int:uid>/authorizations"
  },
  "POST /api/admin/departments": {
    "method": "POST",
    "path": "/api/admin/departments"
  },
  "PUT /api/admin/departments/<int:did>": {
    "method": "PUT",
    "path": "/api/admin/departments/<int:did>"
  },
  "DELETE /api/admin/departments/<int:did>": {
    "method": "DELETE",
    "path": "/api/admin/departments/<int:did>"
  },
  "POST /api/admin/users/<int:uid>/grants": {
    "method": "POST",
    "path": "/api/admin/users/<int:uid>/grants"
  },
  "DELETE /api/admin/users/<int:uid>/grants/<int:dept_id>": {
    "method": "DELETE",
    "path": "/api/admin/users/<int:uid>/grants/<int:dept_id>"
  },
  "GET /api/admin/cnas/batches": {
    "method": "GET",
    "path": "/api/admin/cnas/batches"
  },
  "GET /api/admin/cnas/batches/<int:batch_id>/entries": {
    "method": "GET",
    "path": "/api/admin/cnas/batches/<int:batch_id>/entries"
  },
  "PUT /api/admin/cnas/entries/<int:entry_id>/departments": {
    "method": "PUT",
    "path": "/api/admin/cnas/entries/<int:entry_id>/departments"
  },
  "POST /api/admin/cnas/batches/<int:batch_id>/activate": {
    "method": "POST",
    "path": "/api/admin/cnas/batches/<int:batch_id>/activate"
  },
  "POST /api/ai/search": {
    "method": "POST",
    "path": "/api/ai/search"
  },
  "POST /api/ai/chat/stream": {
    "method": "POST",
    "path": "/api/ai/chat/stream"
  },
  "GET /api/ai/analysis/templates": {
    "method": "GET",
    "path": "/api/ai/analysis/templates"
  },
  "GET /api/ai/suggestions": {
    "method": "GET",
    "path": "/api/ai/suggestions"
  },
  "POST /api/ai/feedback": {
    "method": "POST",
    "path": "/api/ai/feedback"
  },
  "POST /api/ai/transcriptions": {
    "method": "POST",
    "path": "/api/ai/transcriptions"
  },
  "POST /api/ai/form-drafts": {
    "method": "POST",
    "path": "/api/ai/form-drafts"
  },
  "POST /api/ai/form-drafts/apply-audit": {
    "method": "POST",
    "path": "/api/ai/form-drafts/apply-audit"
  },
  "GET /api/ai/dictionary": {
    "method": "GET",
    "path": "/api/ai/dictionary"
  },
  "PUT /api/ai/dictionary": {
    "method": "PUT",
    "path": "/api/ai/dictionary"
  },
  "GET /api/ai/index/status": {
    "method": "GET",
    "path": "/api/ai/index/status"
  },
  "GET /api/reports/<report_no>/attachments": {
    "method": "GET",
    "path": "/api/reports/<report_no>/attachments"
  },
  "POST /api/reports/<report_no>/attachments": {
    "method": "POST",
    "path": "/api/reports/<report_no>/attachments"
  },
  "GET /api/reports/<report_no>/complete-preview-state": {
    "method": "GET",
    "path": "/api/reports/<report_no>/complete-preview-state"
  },
  "POST /api/reports/<report_no>/complete-preview-state": {
    "method": "POST",
    "path": "/api/reports/<report_no>/complete-preview-state"
  },
  "GET /api/reports/<report_no>/complete-preview": {
    "method": "GET",
    "path": "/api/reports/<report_no>/complete-preview"
  },
  "GET /api/attachments/<int:aid>": {
    "method": "GET",
    "path": "/api/attachments/<int:aid>"
  },
  "DELETE /api/attachments/<int:aid>": {
    "method": "DELETE",
    "path": "/api/attachments/<int:aid>"
  },
  "POST /api/auth/login": {
    "method": "POST",
    "path": "/api/auth/login"
  },
  "POST /api/auth/change-password": {
    "method": "POST",
    "path": "/api/auth/change-password"
  },
  "GET /api/auth/profile": {
    "method": "GET",
    "path": "/api/auth/profile"
  },
  "GET /api/auth/captcha": {
    "method": "GET",
    "path": "/api/auth/captcha"
  },
  "GET /api/experiments/bim-cad/status": {
    "method": "GET",
    "path": "/api/experiments/bim-cad/status"
  },
  "POST /api/experiments/bim-cad/recognize": {
    "method": "POST",
    "path": "/api/experiments/bim-cad/recognize"
  },
  "POST /api/experiments/bim-cad/simulate": {
    "method": "POST",
    "path": "/api/experiments/bim-cad/simulate"
  },
  "GET /api/business-supplement/subprojects": {
    "method": "GET",
    "path": "/api/business-supplement/subprojects"
  },
  "POST /api/business-supplement/subprojects": {
    "method": "POST",
    "path": "/api/business-supplement/subprojects"
  },
  "PUT /api/business-supplement/subprojects/<int:item_id>": {
    "method": "PUT",
    "path": "/api/business-supplement/subprojects/<int:item_id>"
  },
  "GET /api/business-supplement/roster-binding/<int:user_id>": {
    "method": "GET",
    "path": "/api/business-supplement/roster-binding/<int:user_id>"
  },
  "POST /api/business-supplement/roster-binding/<int:user_id>": {
    "method": "POST",
    "path": "/api/business-supplement/roster-binding/<int:user_id>"
  },
  "GET /api/business-supplement/roster-binding/me": {
    "method": "GET",
    "path": "/api/business-supplement/roster-binding/me"
  },
  "POST /api/business-supplement/roster-binding/me": {
    "method": "POST",
    "path": "/api/business-supplement/roster-binding/me"
  },
  "GET /api/customers/search": {
    "method": "GET",
    "path": "/api/customers/search"
  },
  "POST /api/eln/launch": {
    "method": "POST",
    "path": "/api/eln/launch"
  },
  "POST /api/eln/session/login": {
    "method": "POST",
    "path": "/api/eln/session/login"
  },
  "POST /api/eln/session/exchange": {
    "method": "POST",
    "path": "/api/eln/session/exchange"
  },
  "GET /api/eln/session": {
    "method": "GET",
    "path": "/api/eln/session"
  },
  "POST /api/eln/session/logout": {
    "method": "POST",
    "path": "/api/eln/session/logout"
  },
  "GET /api/eln/tasks": {
    "method": "GET",
    "path": "/api/eln/tasks"
  },
  "GET /api/eln/tasks/<report_no>": {
    "method": "GET",
    "path": "/api/eln/tasks/<report_no>"
  },
  "POST /api/eln/tasks/<report_no>/records": {
    "method": "POST",
    "path": "/api/eln/tasks/<report_no>/records"
  },
  "PUT /api/eln/records/<external_id>": {
    "method": "PUT",
    "path": "/api/eln/records/<external_id>"
  },
  "POST /api/eln/records/<external_id>/submit": {
    "method": "POST",
    "path": "/api/eln/records/<external_id>/submit"
  },
  "GET /api/eln/reviews": {
    "method": "GET",
    "path": "/api/eln/reviews"
  },
  "POST /api/eln/records/<external_id>/review": {
    "method": "POST",
    "path": "/api/eln/records/<external_id>/review"
  },
  "GET /api/eln/records/<external_id>/pdf": {
    "method": "GET",
    "path": "/api/eln/records/<external_id>/pdf"
  },
  "GET /api/eln/reports/<report_no>/status": {
    "method": "GET",
    "path": "/api/eln/reports/<report_no>/status"
  },
  "GET /api/eln/reports/<report_no>/draft": {
    "method": "GET",
    "path": "/api/eln/reports/<report_no>/draft"
  },
  "GET /api/eln/admin/projects": {
    "method": "GET",
    "path": "/api/eln/admin/projects"
  },
  "PUT /api/eln/admin/projects/<int:project_id>/config": {
    "method": "PUT",
    "path": "/api/eln/admin/projects/<int:project_id>/config"
  },
  "GET /api/eln/admin/templates": {
    "method": "GET",
    "path": "/api/eln/admin/templates"
  },
  "POST /api/eln/admin/templates": {
    "method": "POST",
    "path": "/api/eln/admin/templates"
  },
  "POST /api/eln/admin/templates/<int:template_id>/publish": {
    "method": "POST",
    "path": "/api/eln/admin/templates/<int:template_id>/publish"
  },
  "GET /api/integrations/eln/v1/health": {
    "method": "GET",
    "path": "/api/integrations/eln/v1/health"
  },
  "GET /api/integrations/eln/v1/tasks": {
    "method": "GET",
    "path": "/api/integrations/eln/v1/tasks"
  },
  "GET /api/integrations/eln/v1/tasks/<report_no>": {
    "method": "GET",
    "path": "/api/integrations/eln/v1/tasks/<report_no>"
  },
  "POST /api/integrations/eln/v1/tasks/<report_no>/original-record": {
    "method": "POST",
    "path": "/api/integrations/eln/v1/tasks/<report_no>/original-record"
  },
  "GET /api/entrust/next-no": {
    "method": "GET",
    "path": "/api/entrust/next-no"
  },
  "POST /api/entrust/create": {
    "method": "POST",
    "path": "/api/entrust/create"
  },
  "POST /api/entrust/<int:eid>/complete": {
    "method": "POST",
    "path": "/api/entrust/<int:eid>/complete"
  },
  "POST /api/entrust/<int:eid>/uncomplete": {
    "method": "POST",
    "path": "/api/entrust/<int:eid>/uncomplete"
  },
  "PUT /api/entrust/<int:eid>": {
    "method": "PUT",
    "path": "/api/entrust/<int:eid>"
  },
  "GET /api/entrust/<int:eid>/print": {
    "method": "GET",
    "path": "/api/entrust/<int:eid>/print"
  },
  "POST /api/entrust/query": {
    "method": "POST",
    "path": "/api/entrust/query"
  },
  "GET /api/entrust/handle-departments": {
    "method": "GET",
    "path": "/api/entrust/handle-departments"
  },
  "GET /api/entrust/options": {
    "method": "GET",
    "path": "/api/entrust/options"
  },
  "GET /api/esign/status": {
    "method": "GET",
    "path": "/api/esign/status"
  },
  "GET /api/esign/me": {
    "method": "GET",
    "path": "/api/esign/me"
  },
  "GET /api/esign/tasks": {
    "method": "GET",
    "path": "/api/esign/tasks"
  },
  "POST /api/esign/tasks/<int:flow_id>/sign-url": {
    "method": "POST",
    "path": "/api/esign/tasks/<int:flow_id>/sign-url"
  },
  "POST /api/esign/tasks/batch-sign-url": {
    "method": "POST",
    "path": "/api/esign/tasks/batch-sign-url"
  },
  "GET /api/esign/reports/<path:report_no>": {
    "method": "GET",
    "path": "/api/esign/reports/<path:report_no>"
  },
  "POST /api/esign/reports/<path:report_no>/prepare": {
    "method": "POST",
    "path": "/api/esign/reports/<path:report_no>/prepare"
  },
  "POST /api/esign/reports/<path:report_no>/organization-seal": {
    "method": "POST",
    "path": "/api/esign/reports/<path:report_no>/organization-seal"
  },
  "POST /api/esign/flows/<int:flow_id>/dispatch": {
    "method": "POST",
    "path": "/api/esign/flows/<int:flow_id>/dispatch"
  },
  "GET /api/esign/flows/<int:flow_id>/signed-pdf": {
    "method": "GET",
    "path": "/api/esign/flows/<int:flow_id>/signed-pdf"
  },
  "POST /api/esign/flows/<int:flow_id>/positioning-url": {
    "method": "POST",
    "path": "/api/esign/flows/<int:flow_id>/positioning-url"
  },
  "GET /api/esign/admin/bindings": {
    "method": "GET",
    "path": "/api/esign/admin/bindings"
  },
  "GET /api/esign/admin/bindings/<int:user_id>": {
    "method": "GET",
    "path": "/api/esign/admin/bindings/<int:user_id>"
  },
  "PUT /api/esign/admin/bindings/<int:user_id>": {
    "method": "PUT",
    "path": "/api/esign/admin/bindings/<int:user_id>"
  },
  "POST /api/esign/callback": {
    "method": "POST",
    "path": "/api/esign/callback"
  },
  "POST /api/exports/xlsx": {
    "method": "POST",
    "path": "/api/exports/xlsx"
  },
  "GET /api/erp/contracts": {
    "method": "GET",
    "path": "/api/erp/contracts"
  },
  "GET /api/erp-subprojects/options": {
    "method": "GET",
    "path": "/api/erp-subprojects/options"
  },
  "GET /api/admin/permission-templates": {
    "method": "GET",
    "path": "/api/admin/permission-templates"
  },
  "POST /api/admin/permission-templates": {
    "method": "POST",
    "path": "/api/admin/permission-templates"
  },
  "PUT /api/admin/permission-templates/<int:template_id>": {
    "method": "PUT",
    "path": "/api/admin/permission-templates/<int:template_id>"
  },
  "DELETE /api/admin/permission-templates/<int:template_id>": {
    "method": "DELETE",
    "path": "/api/admin/permission-templates/<int:template_id>"
  },
  "GET /api/admin/permission-templates/export": {
    "method": "GET",
    "path": "/api/admin/permission-templates/export"
  },
  "POST /api/admin/permission-templates/import": {
    "method": "POST",
    "path": "/api/admin/permission-templates/import"
  },
  "POST /api/admin/permission-templates/appointment-import/preview": {
    "method": "POST",
    "path": "/api/admin/permission-templates/appointment-import/preview"
  },
  "POST /api/admin/permission-templates/appointment-import/apply": {
    "method": "POST",
    "path": "/api/admin/permission-templates/appointment-import/apply"
  },
  "GET /api/public/v1/system/status": {
    "method": "GET",
    "path": "/api/public/v1/system/status"
  },
  "GET /api/public/v1/schemes": {
    "method": "GET",
    "path": "/api/public/v1/schemes"
  },
  "GET /api/public/v1/schemes/<string:slug>": {
    "method": "GET",
    "path": "/api/public/v1/schemes/<string:slug>"
  },
  "GET /api/public/v1/schemes/image-credits": {
    "method": "GET",
    "path": "/api/public/v1/schemes/image-credits"
  },
  "GET /api/public/v1/reports/query": {
    "method": "GET",
    "path": "/api/public/v1/reports/query"
  },
  "POST /api/public/v1/quotes/estimate": {
    "method": "POST",
    "path": "/api/public/v1/quotes/estimate"
  },
  "POST /api/public/v1/auth/register": {
    "method": "POST",
    "path": "/api/public/v1/auth/register"
  },
  "POST /api/public/v1/auth/login": {
    "method": "POST",
    "path": "/api/public/v1/auth/login"
  },
  "GET /api/public/v1/auth/me": {
    "method": "GET",
    "path": "/api/public/v1/auth/me"
  },
  "GET /api/public/v1/workspace": {
    "method": "GET",
    "path": "/api/public/v1/workspace"
  },
  "GET /api/public/v1/assistant/status": {
    "method": "GET",
    "path": "/api/public/v1/assistant/status"
  },
  "POST /api/public/v1/assistant/search": {
    "method": "POST",
    "path": "/api/public/v1/assistant/search"
  },
  "POST /api/public/v1/assistant/transcriptions": {
    "method": "POST",
    "path": "/api/public/v1/assistant/transcriptions"
  },
  "GET /api/public/v1/documents/reports/<string:report_no>/download": {
    "method": "GET",
    "path": "/api/public/v1/documents/reports/<string:report_no>/download"
  },
  "GET /api/public/v1/documents/<int:document_id>/download": {
    "method": "GET",
    "path": "/api/public/v1/documents/<int:document_id>/download"
  },
  "GET /api/public/v1/notifications": {
    "method": "GET",
    "path": "/api/public/v1/notifications"
  },
  "POST /api/public/v1/notifications/read-all": {
    "method": "POST",
    "path": "/api/public/v1/notifications/read-all"
  },
  "POST /api/public/v1/notifications/<int:notification_id>/read": {
    "method": "POST",
    "path": "/api/public/v1/notifications/<int:notification_id>/read"
  },
  "POST /api/public/v1/entrusts": {
    "method": "POST",
    "path": "/api/public/v1/entrusts"
  },
  "GET /api/public/v1/entrusts": {
    "method": "GET",
    "path": "/api/public/v1/entrusts"
  },
  "GET /api/public/v1/entrusts/<string:application_no>": {
    "method": "GET",
    "path": "/api/public/v1/entrusts/<string:application_no>"
  },
  "PUT /api/public/v1/entrusts/<string:application_no>": {
    "method": "PUT",
    "path": "/api/public/v1/entrusts/<string:application_no>"
  },
  "PATCH /api/public/v1/entrusts/<string:application_no>": {
    "method": "PATCH",
    "path": "/api/public/v1/entrusts/<string:application_no>"
  },
  "POST /api/public/v1/entrusts/<string:application_no>/submit": {
    "method": "POST",
    "path": "/api/public/v1/entrusts/<string:application_no>/submit"
  },
  "POST /api/public/v1/entrusts/<string:application_no>/cancel": {
    "method": "POST",
    "path": "/api/public/v1/entrusts/<string:application_no>/cancel"
  },
  "DELETE /api/public/v1/entrusts/<string:application_no>": {
    "method": "DELETE",
    "path": "/api/public/v1/entrusts/<string:application_no>"
  },
  "GET /api/admin/external-entrustments": {
    "method": "GET",
    "path": "/api/admin/external-entrustments"
  },
  "POST /api/admin/external-entrustments/<int:application_id>/accept": {
    "method": "POST",
    "path": "/api/admin/external-entrustments/<int:application_id>/accept"
  },
  "POST /api/admin/external-entrustments/<int:application_id>/reject": {
    "method": "POST",
    "path": "/api/admin/external-entrustments/<int:application_id>/reject"
  },
  "GET /api/admin/external-entrustments/<int:application_id>/customer-services": {
    "method": "GET",
    "path": "/api/admin/external-entrustments/<int:application_id>/customer-services"
  },
  "POST /api/admin/external-entrustments/<int:application_id>/customer-documents": {
    "method": "POST",
    "path": "/api/admin/external-entrustments/<int:application_id>/customer-documents"
  },
  "DELETE /api/admin/external-entrustments/<int:application_id>/customer-documents/<int:document_id>": {
    "method": "DELETE",
    "path": "/api/admin/external-entrustments/<int:application_id>/customer-documents/<int:document_id>"
  },
  "POST /api/admin/external-entrustments/<int:application_id>/customer-shipments": {
    "method": "POST",
    "path": "/api/admin/external-entrustments/<int:application_id>/customer-shipments"
  },
  "POST /api/admin/external-entrustments/<int:application_id>/customer-notifications": {
    "method": "POST",
    "path": "/api/admin/external-entrustments/<int:application_id>/customer-notifications"
  },
  "GET /api/quality/instruments": {
    "method": "GET",
    "path": "/api/quality/instruments"
  },
  "GET /api/quality/instruments/<code>/validity": {
    "method": "GET",
    "path": "/api/quality/instruments/<code>/validity"
  },
  "GET /api/quality/qualifications/<int:qid>/validity": {
    "method": "GET",
    "path": "/api/quality/qualifications/<int:qid>/validity"
  },
  "GET /api/quality/standards": {
    "method": "GET",
    "path": "/api/quality/standards"
  },
  "POST /api/quality/standards": {
    "method": "POST",
    "path": "/api/quality/standards"
  },
  "PUT /api/quality/standards/<int:sid>": {
    "method": "PUT",
    "path": "/api/quality/standards/<int:sid>"
  },
  "DELETE /api/quality/standards/<int:sid>": {
    "method": "DELETE",
    "path": "/api/quality/standards/<int:sid>"
  },
  "GET /api/quality/dept-options": {
    "method": "GET",
    "path": "/api/quality/dept-options"
  },
  "GET /api/quality/perm-options": {
    "method": "GET",
    "path": "/api/quality/perm-options"
  },
  "GET /api/quality/personnel": {
    "method": "GET",
    "path": "/api/quality/personnel"
  },
  "GET /api/quality/personnel/export": {
    "method": "GET",
    "path": "/api/quality/personnel/export"
  },
  "GET /api/quality/personnel/template": {
    "method": "GET",
    "path": "/api/quality/personnel/template"
  },
  "POST /api/quality/personnel/import-preview": {
    "method": "POST",
    "path": "/api/quality/personnel/import-preview"
  },
  "POST /api/quality/personnel/import": {
    "method": "POST",
    "path": "/api/quality/personnel/import"
  },
  "GET /api/quality/personnel/<int:pid>": {
    "method": "GET",
    "path": "/api/quality/personnel/<int:pid>"
  },
  "POST /api/quality/personnel": {
    "method": "POST",
    "path": "/api/quality/personnel"
  },
  "PUT /api/quality/personnel/<int:pid>": {
    "method": "PUT",
    "path": "/api/quality/personnel/<int:pid>"
  },
  "DELETE /api/quality/personnel/<int:pid>": {
    "method": "DELETE",
    "path": "/api/quality/personnel/<int:pid>"
  },
  "GET /api/quality/std-library": {
    "method": "GET",
    "path": "/api/quality/std-library"
  },
  "GET /api/quality/std-library/judgment-search": {
    "method": "GET",
    "path": "/api/quality/std-library/judgment-search"
  },
  "GET /api/quality/std-library/search": {
    "method": "GET",
    "path": "/api/quality/std-library/search"
  },
  "GET /api/quality/std-library/template": {
    "method": "GET",
    "path": "/api/quality/std-library/template"
  },
  "GET /api/quality/std-library/export": {
    "method": "GET",
    "path": "/api/quality/std-library/export"
  },
  "POST /api/quality/std-library/import": {
    "method": "POST",
    "path": "/api/quality/std-library/import"
  },
  "GET /api/quality/std-library/<int:sid>": {
    "method": "GET",
    "path": "/api/quality/std-library/<int:sid>"
  },
  "POST /api/quality/std-library": {
    "method": "POST",
    "path": "/api/quality/std-library"
  },
  "PUT /api/quality/std-library/<int:sid>": {
    "method": "PUT",
    "path": "/api/quality/std-library/<int:sid>"
  },
  "PUT /api/quality/std-library/<int:sid>/departments": {
    "method": "PUT",
    "path": "/api/quality/std-library/<int:sid>/departments"
  },
  "DELETE /api/quality/std-library/<int:sid>": {
    "method": "DELETE",
    "path": "/api/quality/std-library/<int:sid>"
  },
  "POST /api/quality/std-library/<int:sid>/void": {
    "method": "POST",
    "path": "/api/quality/std-library/<int:sid>/void"
  },
  "GET /api/quality/equipment": {
    "method": "GET",
    "path": "/api/quality/equipment"
  },
  "GET /api/quality/equipment/<int:eid>": {
    "method": "GET",
    "path": "/api/quality/equipment/<int:eid>"
  },
  "POST /api/quality/equipment": {
    "method": "POST",
    "path": "/api/quality/equipment"
  },
  "PUT /api/quality/equipment/<int:eid>": {
    "method": "PUT",
    "path": "/api/quality/equipment/<int:eid>"
  },
  "DELETE /api/quality/equipment/<int:eid>": {
    "method": "DELETE",
    "path": "/api/quality/equipment/<int:eid>"
  },
  "POST /api/quality/equipment/batch-update": {
    "method": "POST",
    "path": "/api/quality/equipment/batch-update"
  },
  "POST /api/quality/equipment/batch-delete": {
    "method": "POST",
    "path": "/api/quality/equipment/batch-delete"
  },
  "GET /api/quality/equipment/template": {
    "method": "GET",
    "path": "/api/quality/equipment/template"
  },
  "GET /api/quality/equipment/export": {
    "method": "GET",
    "path": "/api/quality/equipment/export"
  },
  "POST /api/quality/equipment/import": {
    "method": "POST",
    "path": "/api/quality/equipment/import"
  },
  "GET /api/quality/equipment/<int:eid>/history": {
    "method": "GET",
    "path": "/api/quality/equipment/<int:eid>/history"
  },
  "POST /api/reports/create": {
    "method": "POST",
    "path": "/api/reports/create"
  },
  "POST /api/reports/<report_no>/sample-reg": {
    "method": "POST",
    "path": "/api/reports/<report_no>/sample-reg"
  },
  "POST /api/reports/<report_no>/correction-requests": {
    "method": "POST",
    "path": "/api/reports/<report_no>/correction-requests"
  },
  "GET /api/reports/<report_no>/correction-requests": {
    "method": "GET",
    "path": "/api/reports/<report_no>/correction-requests"
  },
  "POST /api/reports/correction-requests/<int:request_id>/decision": {
    "method": "POST",
    "path": "/api/reports/correction-requests/<int:request_id>/decision"
  },
  "POST /api/reports/derivable": {
    "method": "POST",
    "path": "/api/reports/derivable"
  },
  "POST /api/reports/cover-preview": {
    "method": "POST",
    "path": "/api/reports/cover-preview"
  },
  "GET /api/reports/<report_no>/cover": {
    "method": "GET",
    "path": "/api/reports/<report_no>/cover"
  },
  "POST /api/reports/lib/standards": {
    "method": "POST",
    "path": "/api/reports/lib/standards"
  },
  "POST /api/reports/lib/schemes": {
    "method": "POST",
    "path": "/api/reports/lib/schemes"
  },
  "POST /api/reports/lib/validate-sample": {
    "method": "POST",
    "path": "/api/reports/lib/validate-sample"
  },
  "POST /api/reports/lib/items": {
    "method": "POST",
    "path": "/api/reports/lib/items"
  },
  "POST /api/reports/lib/capability-items": {
    "method": "POST",
    "path": "/api/reports/lib/capability-items"
  },
  "POST /api/reports/<report_no>/contract-review": {
    "method": "POST",
    "path": "/api/reports/<report_no>/contract-review"
  },
  "PUT /api/reports/<report_no>/edit": {
    "method": "PUT",
    "path": "/api/reports/<report_no>/edit"
  },
  "POST /api/reports/<report_no>/change-resubmit": {
    "method": "POST",
    "path": "/api/reports/<report_no>/change-resubmit"
  },
  "POST /api/reports/<report_no>/change-save": {
    "method": "POST",
    "path": "/api/reports/<report_no>/change-save"
  },
  "POST /api/reports/<report_no>/request-change": {
    "method": "POST",
    "path": "/api/reports/<report_no>/request-change"
  },
  "POST /api/reports/<report_no>/change-test-complete": {
    "method": "POST",
    "path": "/api/reports/<report_no>/change-test-complete"
  },
  "PUT /api/reports/<report_no>/report-pages": {
    "method": "PUT",
    "path": "/api/reports/<report_no>/report-pages"
  },
  "GET /api/reports/<report_no>/authorized-people": {
    "method": "GET",
    "path": "/api/reports/<report_no>/authorized-people"
  },
  "PUT /api/reports/<report_no>/testinfo": {
    "method": "PUT",
    "path": "/api/reports/<report_no>/testinfo"
  },
  "POST /api/reports/<report_no>/testinfo-complete": {
    "method": "POST",
    "path": "/api/reports/<report_no>/testinfo-complete"
  },
  "POST /api/reports/query": {
    "method": "POST",
    "path": "/api/reports/query"
  },
  "GET /api/reports/<report_no>/compliance-preflight": {
    "method": "GET",
    "path": "/api/reports/<report_no>/compliance-preflight"
  },
  "GET /api/reports/<report_no>": {
    "method": "GET",
    "path": "/api/reports/<report_no>"
  },
  "POST /api/reports/<report_no>/action": {
    "method": "POST",
    "path": "/api/reports/<report_no>/action"
  },
  "GET /api/reports/<report_no>/scope-review": {
    "method": "GET",
    "path": "/api/reports/<report_no>/scope-review"
  },
  "POST /api/reports/<report_no>/scope-review": {
    "method": "POST",
    "path": "/api/reports/<report_no>/scope-review"
  },
  "POST /api/report-assurance/batch-sign-url": {
    "method": "POST",
    "path": "/api/report-assurance/batch-sign-url"
  },
  "GET /api/report-assurance/reports/<report_no>/artifact": {
    "method": "GET",
    "path": "/api/report-assurance/reports/<report_no>/artifact"
  },
  "GET /api/report-assurance/reports/<report_no>/signing-history": {
    "method": "GET",
    "path": "/api/report-assurance/reports/<report_no>/signing-history"
  },
  "GET /api/report-assurance/reports/<report_no>/signing-history/<int:flow_id>/file": {
    "method": "GET",
    "path": "/api/report-assurance/reports/<report_no>/signing-history/<int:flow_id>/file"
  },
  "GET /api/report-assurance/bindings": {
    "method": "GET",
    "path": "/api/report-assurance/bindings"
  },
  "POST /api/report-assurance/bindings/<int:user_id>/rebind": {
    "method": "POST",
    "path": "/api/report-assurance/bindings/<int:user_id>/rebind"
  },
  "POST /api/report-assurance/bindings/<int:user_id>/sync": {
    "method": "POST",
    "path": "/api/report-assurance/bindings/<int:user_id>/sync"
  },
  "GET /api/reports/template-profiles": {
    "method": "GET",
    "path": "/api/reports/template-profiles"
  },
  "GET /api/reports/docparser-template-options": {
    "method": "GET",
    "path": "/api/reports/docparser-template-options"
  },
  "POST /api/reports/<report_no>/prepare-query": {
    "method": "POST",
    "path": "/api/reports/<report_no>/prepare-query"
  },
  "GET /api/reports/<report_no>/document-preflight": {
    "method": "GET",
    "path": "/api/reports/<report_no>/document-preflight"
  },
  "GET /api/reports/<report_no>/authoring-template": {
    "method": "GET",
    "path": "/api/reports/<report_no>/authoring-template"
  },
  "GET /api/reports/<report_no>/continuation-template": {
    "method": "GET",
    "path": "/api/reports/<report_no>/continuation-template"
  },
  "GET /api/reports/<report_no>/document-content": {
    "method": "GET",
    "path": "/api/reports/<report_no>/document-content"
  },
  "PUT /api/reports/<report_no>/document-content": {
    "method": "PUT",
    "path": "/api/reports/<report_no>/document-content"
  },
  "POST /api/reports/<report_no>/document-jobs": {
    "method": "POST",
    "path": "/api/reports/<report_no>/document-jobs"
  },
  "GET /api/reports/<report_no>/document-jobs/<job_id>": {
    "method": "GET",
    "path": "/api/reports/<report_no>/document-jobs/<job_id>"
  },
  "GET /api/reports/<report_no>/document-versions": {
    "method": "GET",
    "path": "/api/reports/<report_no>/document-versions"
  },
  "GET /api/reports/<report_no>/document-versions/<int:version_id>/file": {
    "method": "GET",
    "path": "/api/reports/<report_no>/document-versions/<int:version_id>/file"
  },
  "GET /api/reports/<report_no>/document-audits": {
    "method": "GET",
    "path": "/api/reports/<report_no>/document-audits"
  },
  "GET /api/report-publication/reports/<report_no>": {
    "method": "GET",
    "path": "/api/report-publication/reports/<report_no>"
  },
  "POST /api/report-publication/reports/<report_no>": {
    "method": "POST",
    "path": "/api/report-publication/reports/<report_no>"
  },
  "POST /api/report-publication/lookup": {
    "method": "POST",
    "path": "/api/report-publication/lookup"
  },
  "POST /api/report-publication/download": {
    "method": "POST",
    "path": "/api/report-publication/download"
  },
  "GET /api/report-publication/query": {
    "method": "GET",
    "path": "/api/report-publication/query"
  },
  "POST /api/samples/entrust-preview": {
    "method": "POST",
    "path": "/api/samples/entrust-preview"
  },
  "POST /api/samples/<report_no>/void": {
    "method": "POST",
    "path": "/api/samples/<report_no>/void"
  },
  "POST /api/samples/copy-sources/query": {
    "method": "POST",
    "path": "/api/samples/copy-sources/query"
  },
  "GET /api/samples/copy-sources/<report_no>": {
    "method": "GET",
    "path": "/api/samples/copy-sources/<report_no>"
  },
  "POST /api/samples/query": {
    "method": "POST",
    "path": "/api/samples/query"
  },
  "GET /api/samples/entrust-preview-jobs/<ticket>": {
    "method": "GET",
    "path": "/api/samples/entrust-preview-jobs/<ticket>"
  },
  "GET /api/samples/<report_no>/print": {
    "method": "GET",
    "path": "/api/samples/<report_no>/print"
  },
  "POST /api/samples/<report_no>/inbound": {
    "method": "POST",
    "path": "/api/samples/<report_no>/inbound"
  },
  "POST /api/samples/<report_no>/pickup": {
    "method": "POST",
    "path": "/api/samples/<report_no>/pickup"
  },
  "POST /api/samples/<report_no>/return-stock": {
    "method": "POST",
    "path": "/api/samples/<report_no>/return-stock"
  },
  "POST /api/samples/<report_no>/dispose": {
    "method": "POST",
    "path": "/api/samples/<report_no>/dispose"
  },
  "GET /api/technical-subprojects": {
    "method": "GET",
    "path": "/api/technical-subprojects"
  },
  "GET /api/technical-subprojects/options": {
    "method": "GET",
    "path": "/api/technical-subprojects/options"
  },
  "POST /api/technical-subprojects": {
    "method": "POST",
    "path": "/api/technical-subprojects"
  },
  "PUT /api/technical-subprojects/<int:item_id>": {
    "method": "PUT",
    "path": "/api/technical-subprojects/<int:item_id>"
  },
  "GET /api/contract-display/<number>": {
    "method": "GET",
    "path": "/api/contract-display/<number>"
  },
  "PUT /api/contract-display/<number>": {
    "method": "PUT",
    "path": "/api/contract-display/<number>"
  },
  "POST /api/erp-outbound/reports/<report_no>/one-click": {
    "method": "POST",
    "path": "/api/erp-outbound/reports/<report_no>/one-click"
  },
  "POST /api/erp-outbound/one-click/<key>/advance": {
    "method": "POST",
    "path": "/api/erp-outbound/one-click/<key>/advance"
  },
  "GET /api/erp-outbound/console": {
    "method": "GET",
    "path": "/api/erp-outbound/console"
  },
  "GET /api/erp-outbound/console.js": {
    "method": "GET",
    "path": "/api/erp-outbound/console.js"
  },
  "GET /api/erp-outbound/intakes": {
    "method": "GET",
    "path": "/api/erp-outbound/intakes"
  },
  "GET /api/erp-outbound/intakes/<key>": {
    "method": "GET",
    "path": "/api/erp-outbound/intakes/<key>"
  },
  "POST /api/erp-outbound/intakes/<key>/approve": {
    "method": "POST",
    "path": "/api/erp-outbound/intakes/<key>/approve"
  },
  "POST /api/erp-outbound/intakes/<key>/cancel": {
    "method": "POST",
    "path": "/api/erp-outbound/intakes/<key>/cancel"
  },
  "POST /api/erp-outbound/intakes/<key>/refresh": {
    "method": "POST",
    "path": "/api/erp-outbound/intakes/<key>/refresh"
  },
  "POST /api/erp-outbound/intakes/<key>/reverse": {
    "method": "POST",
    "path": "/api/erp-outbound/intakes/<key>/reverse"
  },
  "POST /api/erp-outbound/intakes/<key>/prepare": {
    "method": "POST",
    "path": "/api/erp-outbound/intakes/<key>/prepare"
  },
  "POST /api/erp-outbound/intakes/<key>/send": {
    "method": "POST",
    "path": "/api/erp-outbound/intakes/<key>/send"
  },
  "POST /api/erp-outbound/intakes/<key>/retry-not-sent": {
    "method": "POST",
    "path": "/api/erp-outbound/intakes/<key>/retry-not-sent"
  },
  "GET /api/auth/security/login-records": {
    "method": "GET",
    "path": "/api/auth/security/login-records"
  },
  "POST /api/auth/security/reset-plan": {
    "method": "POST",
    "path": "/api/auth/security/reset-plan"
  },
  "POST /api/auth/security/reset-plan/<plan_id>/next": {
    "method": "POST",
    "path": "/api/auth/security/reset-plan/<plan_id>/next"
  },
  "POST /api/auth/security/reset-plan/<plan_id>/apply": {
    "method": "POST",
    "path": "/api/auth/security/reset-plan/<plan_id>/apply"
  }
} as const
export type BackendEndpoint = keyof typeof backendCatalog
