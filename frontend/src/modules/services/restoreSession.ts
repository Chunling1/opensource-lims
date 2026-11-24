import { fetchAuthProfile } from './auth'
import { ApiError, clearAccessToken } from './http'
import { readSessionToken } from './sessionToken'
import type { AuthResponse } from './auth'

export async function restoreSession(apply: (value: AuthResponse) => void): Promise<void> {
  if (!readSessionToken()) return
  try { apply(await fetchAuthProfile()) }
  catch (error) {
    if (error instanceof ApiError && (error.status === 401 || String(error.code) === '401')) {
      clearAccessToken()
      return
    }
    // A temporary outage is not an invalid login; retain the token for retry.
    throw error
  }
}
