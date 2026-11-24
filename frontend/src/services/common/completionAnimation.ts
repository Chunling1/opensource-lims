let player: Promise<void> | undefined
let animation: Promise<Record<string, unknown>> | undefined

function loadPlayer() {
  if (customElements.get('lord-icon')) return Promise.resolve()
  if (!player) {
    player = new Promise<void>((resolve, reject) => {
      const script = document.createElement('script')
      script.src = `${import.meta.env.BASE_URL}template/assets/js/pages/plugins/lord-icon-2.1.0.js`
      script.onload = () => customElements.get('lord-icon') ? resolve() : reject(new Error('Animation player unavailable'))
      script.onerror = () => { script.remove(); reject(new Error('Animation player failed to load')) }
      document.head.append(script)
    }).catch(error => { player = undefined; throw error })
  }
  return player
}

export async function loadCompletionAnimation() {
  if (!animation) {
    animation = fetch(`${import.meta.env.BASE_URL}animations/report-complete.json`).then(async response => {
      if (!response.ok) throw new Error('Animation unavailable')
      return await response.json() as Record<string, unknown>
    }).catch(error => { animation = undefined; throw error })
  }
  const [, data] = await Promise.all([loadPlayer(), animation])
  return data
}
