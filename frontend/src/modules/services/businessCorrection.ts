import { ElMessage, ElMessageBox } from 'element-plus'
import { profile } from '../../services/platform/auth'
import { request } from './http'
import { copy, changes, type Correction, type Value } from '../../services/platform/correctionFields'
const snapshots = new Map<string, { actor: string; record: Correction }>()
export const canCorrect = () => !!profile.value?.features?.businessDataCorrection && !profile.value?.features?.businessReadOnly
export async function rememberCorrection(kind: string, id: string | number) {
  if (!canCorrect()) return
  const key = `${kind}/${encodeURIComponent(id)}`
  const actor = profile.value!.account
  snapshots.delete(key)
  const record = await request<Correction>(`/api/admin-corrections/${key}`)
  if (profile.value?.account === actor) snapshots.set(key, { actor, record })
}
function snake(key: string) { return key.replace(/[A-Z]/g, c => '_' + c.toLowerCase()) }
export function formChanges(kind: string, record: Correction, payload: Record<string, any>): Record<string, Value> {
  const draft = copy(record.values)
  if (kind === 'reports' && payload.fullDetail) {
    // Preserve audit/workflow and document metadata absent from the sample form.
    const detail = { ...(draft.detail as Record<string, Value> || {}), ...copy(payload.fullDetail) }
    draft.detail = detail
    const raw = payload.fullDetail.rawSample || {}
    if (raw.sampleNo) draft.sample_no = raw.sampleNo
    if (raw.reportNo) draft.report_no = raw.reportNo
  } else {
    for (const [key, value] of Object.entries(payload)) {
      const column = key === 'range' ? 'meas_range' : snake(key)
      if (!(column in draft) || value === undefined) continue
      draft[column] = column === 'use_depts' && Array.isArray(value) ? value.join('；') : value
    }
    if (kind === 'entrusts' && payload.info?.entrustNo) draft.entrust_no = payload.info.entrustNo
  }
  return changes(record, draft)
}
export async function correctForm<T>(kind: string, id: string | number, payload: Record<string, any>, originalPath?: string): Promise<T> {
  const key = `${kind}/${encodeURIComponent(id)}`
  const snapshot = snapshots.get(key)
  if (!canCorrect() || !snapshot || snapshot.actor !== profile.value?.account) throw Error('修订校验信息未加载，请重新打开表单后保存')
  const patch = formChanges(kind, snapshot.record, payload)
  if (!originalPath && !Object.keys(patch).length) return payload as T
  let reason: string
  try {
    const answer = await ElMessageBox.prompt(snapshot.record.warning + ' 请填写本次修改说明。', '确认管理员修订', {
      type: 'warning', inputType: 'textarea', confirmButtonText: '确认修订并保存', cancelButtonText: '返回修改',
      closeOnClickModal: false, inputValidator: value => String(value || '').trim().length >= 2 && String(value || '').trim().length <= 300 || '请填写2至300字的修改说明',
    })
    reason = answer.value.trim()
  } catch { throw Error('已取消保存，修改内容保留在表单中') }
  if (!canCorrect() || snapshot.actor !== profile.value?.account) throw Error('账号或权限已变化，请重新打开表单')
  const result = await request<T & { message: string }>(originalPath || `/api/admin-corrections/${key}`, { method: 'PUT', body: JSON.stringify(originalPath ? { ...payload, adminCorrection: { revision: snapshot.record.revision, reason, confirmed: true } } : { changes: patch, revision: snapshot.record.revision, reason, confirmed: true }) })
  snapshots.delete(key)
  // Revision returned by the same transaction avoids accepting another user's intervening changes.
  if ((result as any).correctionRevision) snapshots.set(key, { actor: snapshot.actor, record: { ...snapshot.record, values: (result as any).correctionValues || { ...snapshot.record.values, ...patch }, revision: (result as any).correctionRevision } })
  ElMessage.success(result.message)
  return result
}
