<template>
  <div class="row g-3 align-items-start">
    <div class="col-12 col-xl">
      <slot />
    </div>
    <div class="col-12 col-xl-auto">
      <!-- Reserve the same label height as the first field row on wide screens. -->
      <span class="form-label d-none d-xl-block invisible" aria-hidden="true">查询</span>
      <div class="d-flex flex-wrap gap-1"><slot name="actions" /></div>
    </div>
  </div>
</template>

<style scoped>
/* Group related filters by content width; narrow cards wrap in DOM/tab order. */
:deep(.query-fields) {
  display: flex;
  flex-wrap: wrap;
  align-items: start;
  gap: 1rem;
}
:deep(.query-field) { min-width: 0; flex: 1 1 12rem; }
:deep(.query-field--group) { flex: 1 1 14rem; }
:deep(.query-field--search) { flex: 1 1 9rem; }
:deep(.query-field--keyword) { flex: 2 1 12rem; }
:deep(.query-field--status) { flex: 1 1 14rem; }
:deep(.query-field--type) { flex: 0 1 7rem; }
:deep(.query-field--date) { flex: 2 1 22rem; }
@media (max-width: 575.98px) {
  :deep(.query-field) { flex-basis: 100%; }
}
</style>
