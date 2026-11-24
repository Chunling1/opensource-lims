import { onBeforeUnmount, type Ref } from 'vue'
export function useUnsavedChanges(dirty: Readonly<Ref<boolean>>) {
  const listener = (event: BeforeUnloadEvent) => { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
  window.addEventListener('beforeunload', listener)
  onBeforeUnmount(() => window.removeEventListener('beforeunload', listener))
}
