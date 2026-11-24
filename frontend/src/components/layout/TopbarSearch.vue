<script setup lang="ts">
import { normalizeError } from '../../services/common/errors'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { currentActor, canRead } from '../../stores/session'
import { navigation, flattenNavigation } from '../../router/navigation/navigation'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { registrationCanReadSamples } from '../../services/commissions/registrationService'
import { clientYearRange } from '../../services/common/date'
import type { RegistrationSampleRow } from '../../types/commissions/registration'
const props = defineProps<{ mobile?: boolean }>()
const router = useRouter(), route = useRoute(), root = ref<HTMLElement>(), input = ref<HTMLInputElement>()
const keyword = ref(''), open = ref(false), loading = ref(false), error = ref(''), matches = ref<RegistrationSampleRow[]>([]), total = ref(0)
const dates = clientYearRange()
const canSearchSamples = computed(() => canRead(currentActor.value, 'commissions') && registrationCanReadSamples(currentActor.value))
function resultsLocation(term = keyword.value) { return { path: '/commissions/query', query: { scope: 'all', sKeyword: term.trim() || undefined, sCommissionFrom: dates.from, sCommissionTo: dates.to } } }
function sampleLocation(id: string) { return { path: `/commissions/query/samples/${encodeURIComponent(id)}`, query: { returnTo: router.resolve(resultsLocation()).fullPath } } }
const historyKey = 'lims.search.v1', recent = ref<string[]>([])
const pages = computed(() => navigation.flatMap(group => flattenNavigation(group.children).map(item => ({ ...item, label: [...flattenNavigation(group.children, true).filter(parent => parent.children && item.to.startsWith(`${parent.to}/`)).map(parent => parent.label), item.label].join(' / ') }))).filter(item => (!item.module || canRead(currentActor.value, item.module)) && (!keyword.value.trim() || item.label.includes(keyword.value.trim()))).slice(0, 8))
let timer: ReturnType<typeof setTimeout> | undefined, sequence = 0, controller: AbortController | undefined
function invalidate() { sequence++; controller?.abort(); clearTimeout(timer); matches.value = []; total.value = 0; error.value = ''; loading.value = false }
function readRecent() {
  try { const data = JSON.parse(localStorage.getItem(historyKey) || 'null'); recent.value = data?.version === 1 && Array.isArray(data.items) ? data.items.filter((v: unknown) => typeof v === 'string').slice(0, 5) : [] }
  catch { recent.value = [] }
}
function remember() {
  const term = keyword.value.trim()
  if (!term) return
  recent.value = [term, ...recent.value.filter(item => item !== term)].slice(0, 5)
  try { localStorage.setItem(historyKey, JSON.stringify({ version: 1, items: recent.value })) } catch { /* Search remains usable without local history. */ }
}
async function lookup() {
  controller?.abort()
  const request = ++sequence, term = keyword.value.trim()
  error.value = ''; matches.value = []; total.value = 0
  if (!term || !canSearchSamples.value) { loading.value = false; return }
  const abort = new AbortController(); controller = abort
  loading.value = true
  try { const data = await registrationDemo.samples({ keyword: term, commissionFrom: dates.from, commissionTo: dates.to, page: 1, pageSize: 10, sort: 'createdAt', direction: 'desc' }, abort.signal, 'query'); if (request === sequence) { matches.value = data.items.slice(0, 4); total.value = data.total } }
  catch (e) { if (request === sequence && !abort.signal.aborted) error.value = normalizeError(e).message }
  finally { if (request === sequence) loading.value = false }
}
watch(keyword, () => { invalidate(); loading.value = !!keyword.value.trim() && canSearchSamples.value; timer = setTimeout(lookup, 180) }, { flush: 'sync' })
watch(currentActor, () => { invalidate(); if (open.value) void lookup() }, { flush: 'sync' })
watch(() => route.fullPath, () => { open.value = false; invalidate() })
function submit(term = keyword.value) { if (!canSearchSamples.value) return; keyword.value = term; remember(); open.value = false; invalidate(); void router.push(resultsLocation(term)) }
function focus() { readRecent(); open.value = true; lookup() }
function close() { input.value?.focus(); open.value = false; invalidate() }
function clear() { keyword.value = ''; open.value = true; input.value?.focus() }
function outside(event: PointerEvent) { if (!root.value?.contains(event.target as Node)) open.value = false }
function move(event: KeyboardEvent) {
  if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return
  event.preventDefault(); open.value = true
  const targets = Array.from(root.value?.querySelectorAll<HTMLElement>('[data-search-result]') || [])
  const index = targets.indexOf(document.activeElement as HTMLElement)
  targets[(index + (event.key === 'ArrowDown' ? 1 : -1) + targets.length) % targets.length]?.focus()
}
onMounted(() => { readRecent(); document.addEventListener('pointerdown', outside) })
onBeforeUnmount(() => { invalidate(); document.removeEventListener('pointerdown', outside) })
</script>
<template>
  <form ref="root" :class="mobile ? 'p-3' : 'app-search d-none d-md-block'" @submit.prevent="submit()" @keydown.esc.stop.prevent="close" @keydown="move">
    <div :class="mobile ? 'input-group' : 'input-icon'">
      <input ref="input" v-model="keyword" type="text" role="searchbox" class="form-control" :aria-label="mobile ? '手机样品搜索' : '全局样品搜索'" placeholder="搜索样品编号、名称…" maxlength="200" autocomplete="off" :aria-expanded="open" @focus="focus" />
      <button v-if="mobile" class="btn btn-primary" type="submit" aria-label="搜索样品"><i aria-hidden="true" class="ti ti-search"></i></button>
      <template v-else><span class="input-icon-addon"><i aria-hidden="true" class="ti ti-search"></i></span></template>
    </div>
    <div v-if="open" :id="mobile ? 'search-dropdown-responsive' : 'search-dropdown'" :class="mobile ? 'pt-3' : 'dropdown-menu dropdown-menu-lg show'" aria-label="搜索建议">
      <template v-if="canSearchSamples && !keyword.trim() && recent.length"><div class="dropdown-header"><h6 class="text-overflow text-muted mb-0 text-uppercase">最近搜索</h6></div><div class="dropdown-item bg-transparent text-wrap"><button v-for="term in recent" :key="term" data-search-result class="btn btn-secondary-lt btn-sm rounded-pill me-1 mb-1" type="button" @click="submit(term)">{{ term }} <i aria-hidden="true" class="ti ti-search ms-1"></i></button></div></template>
      <template v-if="pages.length"><div class="dropdown-header"><h6 class="text-overflow text-muted mb-1 text-uppercase">页面</h6></div><RouterLink v-for="item in pages" :key="item.to" data-search-result :to="item.to" class="dropdown-item notify-item" @click="open = false"><i aria-hidden="true" class="align-middle fs-3 text-muted me-2" :class="item.icon"></i><span>{{ item.label }}</span></RouterLink></template>
      <template v-if="canSearchSamples && keyword.trim()"><div class="dropdown-header mt-2"><h6 class="text-overflow text-muted mb-1 text-uppercase">样品</h6></div><p v-if="loading" class="text-muted px-3" role="status">正在搜索…</p><div v-else-if="error" class="px-3" role="alert"><p class="text-danger mb-1">{{ error }}</p><button type="button" class="btn btn-sm btn-primary-lt" @click="lookup">重试搜索</button></div><p v-else-if="!matches.length" class="text-muted px-3">暂无匹配样品</p><RouterLink v-for="sample in matches" :key="sample.id" data-search-result :to="sampleLocation(sample.id)" class="dropdown-item notify-item py-2" @click="remember(); open = false"><div class="d-flex"><div class="avatar-xs me-3 flex-shrink-0"><span class="avatar rounded-circle bg-primary-subtle text-primary"><i aria-hidden="true" class="ti ti-flask"></i></span></div><div class="flex-grow-1 overflow-hidden"><h6 class="m-0 text-truncate">{{ sample.name }}</h6><span class="small text-muted">{{ sample.code }}</span></div></div></RouterLink><div class="text-center pt-3 pb-1"><button type="submit" class="btn btn-primary btn-sm">查看全部结果（{{ total }}） <i aria-hidden="true" class="ti ti-arrow-right ms-1"></i></button></div></template>
    </div>
  </form>
</template>
