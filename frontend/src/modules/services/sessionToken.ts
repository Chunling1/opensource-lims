import { getSessionToken, setToken } from '../../services/platform/http'
export const readSessionToken = getSessionToken
export function saveSessionToken(value:string) { setToken(value); if (!value) window.dispatchEvent(new Event('lims-next:unauthorized')) }
