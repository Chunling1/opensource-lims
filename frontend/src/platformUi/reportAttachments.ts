import type {Attachment} from '@/services/attachments'

export interface ReportUploadRequest {
  file: File
  onSuccess?: () => void
  onError?: (error: unknown) => void
}

// Generated covers are not user uploads; provenance preserves same-name uploads.
export function isLegacySystemCover(file: Attachment) {
  return /^系统生成封面\.(docx|pdf)$/i.test(file.name)
    && file.source === '模板生成'
}

// FilePond must never report success when the existing controller caught a failure
// or the user cancelled its replacement confirmation.
export async function runReportUpload(file:File, invoke:(request:ReportUploadRequest)=>Promise<void>) {
  let succeeded=false, failure:unknown
  await invoke({file,onSuccess:()=>{succeeded=true},onError:error=>{failure=error}})
  if(failure) throw failure
  if(!succeeded) throw new Error('未上传：操作已取消或报告已切换，请重新选择文件')
}

export function templateAttachments(files:Attachment[]) {
  return files.map((source,index)=>({
    id:source.id===undefined?`legacy-${index}-${source.name}`:String(source.id),
    name:source.name,type:source.contentType||source.type||'',size:source.sizeBytes||0,source,
  }))
}
