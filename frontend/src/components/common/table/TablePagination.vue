<script setup lang="ts">
import { computed, ref, watch } from 'vue'
const props = defineProps<{ label: string; total: number; page: number; pageSize: number; sizes: number[]; extended?: boolean }>()
const emit = defineEmits<{ page: [number]; size: [number] }>()
const lastPage = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const pageDigits = computed(() => String(lastPage.value).length)
const pageWidthText = computed(() => '8'.repeat(pageDigits.value))
const target = ref(props.page)
watch(() => props.page, value => { target.value = value })
// Bound the visible buttons independently of the server's total record count.
const pages = computed(() => {
  const count = lastPage.value, current = Math.min(count, Math.max(1, props.page))
  // Extended pickers already have first/last controls; keep a constant-size window
  // so the jump form cannot wrap just because a different page became active.
  if (props.extended) {
    const length = Math.min(pageDigits.value > 6 ? 1 : pageDigits.value > 2 ? 3 : 5, count)
    const start = Math.max(1, Math.min(current - Math.floor(length / 2), count - length + 1))
    return Array.from({ length }, (_, index) => start + index)
  }
  const numbers = new Set([1, count])
  const start = Math.max(1, Math.min(current - 1, count - 2))
  for (let n = start; n <= Math.min(count, Math.max(3, current + 1)); n++) numbers.add(n)
  const entries: (number | string)[] = [], sorted = [...numbers].sort((a, b) => a - b)
  for (let index = 0; index < sorted.length; index++) {
    const n = sorted[index]!, previous = sorted[index - 1]
    if (previous !== undefined && n - previous > 1) entries.push(`gap-${previous}`)
    entries.push(n)
  }
  return entries
})
function change(page: number) { if (page !== props.page && page >= 1 && page <= lastPage.value) emit('page', page) }
function jump() { if (Number.isInteger(target.value)) change(target.value) }
</script>
<template>
  <div class="d-flex flex-wrap align-items-center justify-content-between p-3 border-top" :class="extended ? 'gap-2' : 'gap-3'">
    <div class="d-flex align-items-center gap-2 text-nowrap"><span class="text-muted">共 {{ total }} 条</span><label :for="`${label}-size`" class="mb-0">每页</label><select :id="`${label}-size`" :aria-label="`${label}每页条数`" class="form-select form-select-sm w-auto" :value="pageSize" @change="$emit('size', Number(($event.target as HTMLSelectElement).value))"><option v-for="size in sizes" :key="size" :value="size">{{ size }}</option></select></div>
    <nav :aria-label="`${label}分页`" class="pagination-wrap hstack text-nowrap" :class="[extended ? 'flex-nowrap' : 'flex-wrap', extended && pageDigits > 2 ? 'gap-1' : 'gap-2']">
      <button v-if="extended" type="button" class="page-item pagination-prev d-none d-sm-block" :class="{ disabled: page <= 1 }" :disabled="page <= 1" @click="change(1)">首页</button>
      <button type="button" class="page-item pagination-prev" :class="{ disabled: page <= 1 }" :disabled="page <= 1" @click="change(page - 1)">上一页</button>
      <ul class="pagination listjs-pagination justify-content-start mw-100 mb-0" :class="extended ? 'flex-nowrap' : 'flex-wrap'">
        <li v-for="entry in pages" :key="entry" :class="{ active: entry === page, disabled: typeof entry !== 'number', 'd-none d-sm-block': entry !== page }">
          <button v-if="typeof entry === 'number'" type="button" class="page position-relative" :class="{ 'px-1': extended && pageDigits > 2 }" :aria-label="`第 ${entry} 页`" :aria-current="entry === page ? 'page' : undefined" :disabled="!total" @click="change(entry)"><template v-if="extended"><span class="invisible" aria-hidden="true">{{ pageWidthText }}</span><span class="position-absolute top-50 start-50 translate-middle">{{ entry }}</span></template><template v-else>{{ entry }}</template></button>
          <span v-else class="page text-muted" aria-hidden="true">…</span>
        </li>
      </ul>
      <button type="button" class="page-item pagination-next" :class="{ disabled: page >= lastPage }" :disabled="page >= lastPage" @click="change(page + 1)">下一页</button>
      <button v-if="extended" type="button" class="page-item pagination-next d-none d-sm-block" :class="{ disabled: page >= lastPage }" :disabled="page >= lastPage" @click="change(lastPage)">尾页</button>
    </nav>
    <form v-if="extended" class="d-flex align-items-center gap-2" :aria-label="`${label}跳页`" @submit.prevent="jump"><input v-model.number="target" type="number" min="1" :max="lastPage" step="1" required class="form-control form-control-sm w-auto" :aria-label="`${label}页码`" /><button class="btn btn-light btn-sm text-nowrap" type="submit">跳转</button></form>
  </div>
</template>
