import type { RegistrationPage } from './registration'

export interface Manufacturer { id: string; code: string; name: string; type: string }
export interface ManufacturerQuery { code?: string; name?: string; type?: string; page?: number; pageSize?: number }
export interface ManufacturerPage extends RegistrationPage<Manufacturer> { types: string[] }
