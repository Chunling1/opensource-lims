import 'vue-router'
import type { BusinessArea, PageType } from '@/data/modules'

declare module 'vue-router' {
  interface RouteMeta {
    moduleKey?: string
    moduleName?: string
    area?: BusinessArea
    areaName?: string
    pageKey?: string
    pageName?: string
    pageType?: PageType
    permission?: string
    modulePermission?: string
  }
}
