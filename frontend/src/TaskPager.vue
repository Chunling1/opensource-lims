<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
const p = defineProps<{ page: number; total: number; size: number }>()
const route = useRoute(),
  router = useRouter()
const last = computed(() => Math.max(1, Math.ceil(p.total / p.size)))
const pages = computed(() =>
  Array.from(new Set([1, p.page - 1, p.page, p.page + 1, last.value]))
    .filter((i) => i > 0 && i <= last.value)
    .sort((a, b) => a - b),
)
function go(page: number, size = p.size) {
  return router.push({ name: route.name!, query: { ...route.query, page, pageSize: size } })
}
</script>
<template>
  <div class="card-footer d-flex align-items-center gap-2 flex-wrap">
    <span class="text-secondary">共 {{ total }} 条</span
    ><label class="d-flex align-items-center gap-1"
      >每页<select
        class="form-select form-select-sm w-auto"
        :value="size"
        @change="go(1, Number(($event.target as HTMLSelectElement).value))"
      >
        <option v-for="i in [10, 20, 50]" :key="i">{{ i }}</option>
      </select></label
    >
    <nav class="ms-auto" aria-label="分页">
      <ul class="pagination pagination-sm mb-0">
        <li class="page-item">
          <button class="page-link" :disabled="page <= 1" @click="go(page - 1)" aria-label="上一页">
            ‹
          </button>
        </li>
        <template v-for="(n, i) in pages" :key="n"
          ><li v-if="i && n > pages[i - 1] + 1" class="page-item disabled">
            <span class="page-link">…</span>
          </li>
          <li class="page-item" :class="{ active: n === page }">
            <button
              class="page-link"
              :aria-current="n === page ? 'page' : undefined"
              @click="go(n)"
            >
              {{ n }}
            </button>
          </li></template
        >
        <li class="page-item">
          <button
            class="page-link"
            :disabled="page >= last"
            @click="go(page + 1)"
            aria-label="下一页"
          >
            ›
          </button>
        </li>
      </ul>
    </nav>
  </div>
</template>
