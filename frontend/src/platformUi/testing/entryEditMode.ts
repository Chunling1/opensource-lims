import { computed, ref, watch } from 'vue'

type EntryEditContext = {
  open: boolean
  reportNo: string
  account: string
  route: string
  canCorrect: boolean
  requestedReadOnly: boolean
  status: string
  sampleStatus: string
}

// Permission to correct is a capability, never an implicit choice of edit mode.
export function useEntryEditMode(context: () => EntryEditContext) {
  const enabled = ref(false)
  const canAdminEdit = computed(() => context().open && !!context().reportNo && context().canCorrect)
  const adminEditing = computed(() => canAdminEdit.value && enabled.value)
  const formReadOnly = computed(() => {
    const c = context()
    if (adminEditing.value) return false
    return c.requestedReadOnly || !(
      c.status === '检测更改中'
      || (['检测录入中', '退回待重传'].includes(c.status) && c.sampleStatus === '已领取')
    )
  })
  watch([
    () => context().open, () => context().reportNo, () => context().account,
    () => context().route, () => context().canCorrect,
  ], () => { enabled.value = false }, { flush: 'sync' })
  function toggleAdminEditing() {
    if (canAdminEdit.value) enabled.value = !enabled.value
  }
  return { canAdminEdit, adminEditing, formReadOnly, toggleAdminEditing }
}
