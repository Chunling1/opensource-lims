import { applyTheme, restoreTheme } from './settings'
const settings = restoreTheme()
applyTheme(settings)
// Match the Vue initialization view before the application bundle has loaded.
const pending = document.getElementById('boot-pending')
if (pending && document.getElementById('boot-failed')?.hidden !== false) {
  const animation = pending.querySelector<HTMLElement>('#preloader')
  if (animation) animation.hidden = settings.preloader !== 'enable'
  pending.hidden = false
}
