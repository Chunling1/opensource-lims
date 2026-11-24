const VERSION_ENDPOINT = 'version.json'
const RELOAD_ATTEMPT_KEY = 'hn_build_reload_attempt'
const CHECK_INTERVAL_MS = 60_000

interface BuildVersion {
  buildId?: string
}

let checking: Promise<boolean> | null = null
let guardInstalled = false
let lastSuccessfulCheckAt = 0

function versionUrl() {
  const url = new URL(VERSION_ENDPOINT, document.baseURI)
  url.searchParams.set('t', String(Date.now()))
  return url.toString()
}

async function readRemoteBuildId() {
  const response = await fetch(versionUrl(), {
    cache: 'no-store',
    headers: { 'Cache-Control': 'no-cache' },
  })
  if (!response.ok) return ''
  const data = await response.json() as BuildVersion
  return String(data.buildId || '').trim()
}

async function performBuildCheck() {
  if (import.meta.env.DEV) return false
  if (Date.now() - lastSuccessfulCheckAt < CHECK_INTERVAL_MS) return false

  try {
    const remoteBuildId = await readRemoteBuildId()
    if (!remoteBuildId) return false
    lastSuccessfulCheckAt = Date.now()

    if (remoteBuildId === __APP_BUILD_ID__) {
      sessionStorage.removeItem(RELOAD_ATTEMPT_KEY)
      return false
    }

    const attempt = `${__APP_BUILD_ID__}->${remoteBuildId}`
    if (sessionStorage.getItem(RELOAD_ATTEMPT_KEY) === attempt) return false
    sessionStorage.setItem(RELOAD_ATTEMPT_KEY, attempt)

    const target = new URL(window.location.href)
    target.searchParams.set('_build', remoteBuildId)
    window.location.replace(target.toString())
    return true
  } catch {
    // 版本检查失败不能阻断登录或正常业务，下一次聚焦/定时检查会自动重试。
    return false
  }
}

export function checkForBuildUpdate() {
  if (!checking) {
    checking = performBuildCheck().finally(() => {
      checking = null
    })
  }
  return checking
}

export function installBuildUpdateGuard() {
  if (guardInstalled || import.meta.env.DEV) return
  guardInstalled = true

  const check = () => {
    void checkForBuildUpdate()
  }
  window.addEventListener('focus', check)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') check()
  })
  window.setInterval(check, CHECK_INTERVAL_MS)
}
