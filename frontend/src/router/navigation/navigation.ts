import { workbenches } from '../../types/dashboard'
import { samplePages } from './sampleNavigation'
import { testingPages } from './testingNavigation'
import { reportPages } from './reportNavigation'
import { commissionPages } from './commissionNavigation'
import { managementGroups } from './managementNavigation'
import { modules } from '@/data/modules'
export interface NavigationItem { label: string; to: string; icon: string; module?: string; permission?: string; workbench?: string; children?: NavigationItem[] }
export function flattenNavigation(items: NavigationItem[], includeGroups = false): NavigationItem[] {
  return items.flatMap(item => item.children ? [...(includeGroups ? [item] : []), ...flattenNavigation(item.children, includeGroups)] : [item])
}
export function filterNavigation(items: NavigationItem[], allowed: (item: NavigationItem) => boolean): NavigationItem[] {
  return items.flatMap(item => {
    if (!item.children) return allowed(item) ? [item] : []
    const children = filterNavigation(item.children, allowed)
    return children.length ? [{ ...item, children }] : []
  })
}
export const navigationSections = { overview: '概览', business: '业务', management: '管理', analytics: '分析' } as const
export type NavigationSection = keyof typeof navigationSections
export interface NavigationGroup { id: string; label: string; icon: string; section: NavigationSection; children: NavigationItem[] }
const icons: Record<string, string> = { commissions: 'ti ti-file-description', customers: 'ti ti-users-group', samples: 'ti ti-flask', testing: 'ti ti-microscope', reports: 'ti ti-file-certificate', finance: 'ti ti-currency-yen', quality: 'ti ti-shield-check', system: 'ti ti-settings' }
// Top-level entries follow docs/菜单.txt, grouped into contiguous navigation sections.
// Domain service groups do not automatically create navigation entries.
export const templateNavigation: NavigationGroup[] = [
  { id: 'overview', label: '首页', icon: 'ti ti-dashboard', section: 'overview', children: [
    { label: '工作台', to: '/dashboard', icon: 'ti ti-dashboard' },
    { label: '我的待办', to: '/work', icon: 'ti ti-checklist' },
    { label: '通知中心', to: '/notifications', icon: 'ti ti-bell' },
  ] },
  { id: 'commissions', label: '委托管理', icon: icons.commissions!, section: 'business', children: [...commissionPages] },
  { id: 'samples', label: '样品管理', icon: icons.samples!, section: 'business', children: [...samplePages] },
  { id: 'testing', label: '检测管理', icon: icons.testing!, section: 'business', children: [...testingPages] },
  { id: 'reports', label: '报告管理', icon: icons.reports!, section: 'business', children: reportPages },
  ...managementGroups,
]
const originalIcons: Record<string,string> = {dashboard:'ti ti-dashboard',entrust:'ti ti-file-description',sample:'ti ti-flask',testing:'ti ti-microscope',report:'ti ti-file-certificate',finance:'ti ti-currency-yen',quality:'ti ti-shield-check',system:'ti ti-settings',statistics:'ti ti-chart-bar',online_entrust:'ti ti-world',bim_lab:'ti ti-building'}
export const navigation: NavigationGroup[] = modules.map(module=>({
  id:module.key,label:module.name,icon:originalIcons[module.key]||'ti ti-apps',
  section:module.key==='dashboard'?'overview':['entrust','sample','testing','report','online_entrust','bim_lab'].includes(module.key)?'business':module.key==='statistics'?'analytics':'management',
  children:module.pages.filter(page=>!page.hidden).map(page=>({label:page.name,to:page.path,icon:originalIcons[module.key]||'ti ti-apps',permission:page.permission})),
}))
navigation.find(g=>g.id==='dashboard')?.children.push(...workbenches.map(w=>({label:w.title,to:`/dashboard/${w.id}`,icon:w.icon,workbench:w.id})))

// Keep the supplied template's contiguous sidebar sections and workflow order.
const moduleOrder = ['dashboard','entrust','sample','testing','report','quality','system']
navigation.sort((a,b)=>moduleOrder.indexOf(a.id)-moduleOrder.indexOf(b.id))
