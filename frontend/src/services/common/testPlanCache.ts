import { inject, provide, watch, type InjectionKey } from 'vue'
import { useRoute } from 'vue-router'
import { currentActor } from '../../stores/session'

// Cache data, never selection drafts. Reopening a picker must still start from
// its caller's current value, including after a cancelled edit.
export class TestPlanCache {
  private entries = new Map<string, unknown>()
  revision = 0
  get<T>(key: string): T | undefined {
    const value = this.entries.get(key)
    return value === undefined ? undefined : JSON.parse(JSON.stringify(value)) as T
  }
  set<T>(key: string, value: T, revision: number) {
    if (revision === this.revision) this.entries.set(key, JSON.parse(JSON.stringify(value)))
  }
  clear() { this.revision++; this.entries.clear() }
}
const key: InjectionKey<TestPlanCache> = Symbol('page-test-plans')
export function provideTestPlanCache() {
  const route = useRoute(), cache = new TestPlanCache()
  provide(key, cache)
  // Query-string changes are still the same page. Identity/permission changes
  // and navigation discard the cache, including results of older requests.
  watch([() => route.path, () => JSON.stringify(currentActor.value)], () => cache.clear(), { flush: 'sync' })
}
export function useTestPlanCache() { return inject(key, undefined) }
