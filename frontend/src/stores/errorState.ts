import { shallowRef } from 'vue'
import { normalizeError, type AppError } from '../services/common/errors'
export const fatalError = shallowRef<AppError>()
export const navigationError = shallowRef<AppError>()
export const failedDestination = shallowRef('')
export function failApplication(value: unknown) { fatalError.value = normalizeError(value) }
