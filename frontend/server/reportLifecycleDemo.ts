import { prepareReportRelease } from './reportLifecycle'
import { demoSignedReport } from './reportSigning'
import { demoActors } from '../src/services/storage/demoActors'
import type { RegistrationState } from '../src/types/commissions/registration'

// New demo examples only. Never migrate old approved reports by generating new files.
export async function seedReportLifecycleDemo(state: RegistrationState) {
  for (const [index, form] of (['纸质', '纸质', '电子', '电子', '纸质', '电子', '纸质'] as const).entries()) {
    const number = 91 + index
    const sample = state.samples.find(row => row.id === `demo-yp-${number}`)!
    if (sample.reportRelease || sample.reportReleaseHistory?.length) continue
    sample.reportRelease = (await prepareReportRelease(state, sample, demoActors[0]!)).release
    if (index === 1 || index >= 4 && form === '纸质') sample.reportRelease.printStatus = '打印完成'
    if (index === 2 || index === 5) {
      const release = sample.reportRelease, task = release.signing!
      release.signed = await demoSignedReport(release)
      task.status = '签章完成'; task.signature = '已完成'; task.seal = '已完成'
      task.externalId = `demo-${task.key}`; task.updatedAt = new Date().toISOString()
      task.events.push({ at: task.updatedAt, status: task.status, message: '演示签章完成，可登记发放。' })
    }
    if (index >= 4) {
      const release = sample.reportRelease, at = new Date().toISOString(), date = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' })
      release.distributionStatus = '已发放'
      release.receipt = { recipient: '演示领取人', method: form === '纸质' ? '自取' : '其他', date, notes: '', at, actorId: 'admin', actorName: '演示用户' }
      release.history.push({ at, actorId: 'admin', actorName: '演示用户', action: '发放', reason: JSON.stringify(release.receipt) })
      if (index === 6) {
        release.archiveStatus = '已归档'; release.archive = { date, at, actorId: 'admin', actorName: '演示用户' }
        release.history.push({ at, actorId: 'admin', actorName: '演示用户', action: '归档', reason: JSON.stringify(release.archive) })
      }
    }
    if (index === 3) {
      const task = sample.reportRelease.signing!
      task.status = '签章失败'; task.error = '演示：签章服务明确返回失败，请重试。'
      task.events.push({ at: task.updatedAt, status: task.status, message: task.error })
    }
  }
}
