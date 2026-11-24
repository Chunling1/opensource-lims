import {describe, it, expect} from 'vitest'
import {modules} from '@/data/modules'
import {originalPlatformRoutes} from '../../router/modules/originalPlatform'
import {reportRoutes} from '../../router/modules/reports'
import {reportPages} from '../../router/navigation/reportNavigation'
import {dashboardTarget} from '@/utils/dashboardAccess'

describe('issuance followed by archive', () => {
  it('exposes a separate release page after archive', () => {
    const pages=modules.find(m=>m.path==='/inspection/report')!.pages.map(p=>p.key)
    expect(pages.slice(pages.indexOf('signing'),pages.indexOf('signing')+4)).toEqual(['signing','archive','release','query'])
    expect(JSON.stringify(reportPages)).toContain('/reports/distribution')
    expect(originalPlatformRoutes.find(r => r.path === '/inspection/report/release')?.component).toBeTruthy()
    expect(reportRoutes.find(r => r.path === '/reports/distribution')?.redirect).toBe('/inspection/report/release')
  })
  it('routes release tasks independently from archive', () => {
    const row = {status: '待发放', todoView: 'release'} as any
    expect(dashboardTarget(row, p => p === 'report.release.view')).toBe('/inspection/report/release')
    expect(dashboardTarget(row, p => p === 'report.archive.view')).toBeUndefined()
  })
  it.each(['待发放', '已发放'])('routes %s archive tasks with archive permission', status => {
    const row = {status, todoView: 'archive'} as any
    expect(dashboardTarget(row, p => p === 'report.archive.view')).toBe('/inspection/report/archive')
    expect(dashboardTarget(row, p => p === 'report.release.view')).toBeUndefined()
    expect(dashboardTarget({...row, todoView: undefined}, () => true)).toBeUndefined()
    expect(dashboardTarget(row, () => true, true)).toBeUndefined()
  })
})
