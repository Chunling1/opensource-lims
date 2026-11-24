import type { Actor } from '../../types/lims'
import { allowedWorkbench, defaultWorkbench } from '../../types/dashboard'
const key = (actor: Actor) => `lims.workbench.v1.${actor.id}`
export function homeFor(actor: Actor) {
  let saved: string | null = null
  try { saved = localStorage.getItem(key(actor)) } catch { /* Preferences are optional. */ }
  return defaultWorkbench(actor, saved)
}
export function rememberWorkbench(actor: Actor, id: string) {
  if (!allowedWorkbench(actor, id)) return
  try { localStorage.setItem(key(actor), id) } catch { /* Preferences are optional. */ }
}
