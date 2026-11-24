import { request } from './http'

export interface BimCadStatus {
  enabled: boolean
  ready: boolean
  model: string
  modelBenchmark: { name: string; value: number; notice: string }
  modelExists: boolean
  modelVerified: boolean
  modelError: string
  dependencies: Record<string, boolean>
  supportedFiles: string[]
  nativeCadNotice: string
  privacyNotice: string
}

export interface RecognitionMetrics {
  wallLengthPx: number
  windowLengthPx: number
  doorLengthPx: number
  wallAreaPx: number
  windowAreaPx: number
  doorAreaPx: number
  wallComponents: number
  windowComponents: number
  doorComponents: number
}

export interface BimCadRecognition {
  recognitionId: string
  sourceHash: string
  source: {
    sourceType: string
    page: number
    pdfPageCount?: number
    originalWidth: number
    originalHeight: number
    processedWidth: number
    processedHeight: number
    resized: boolean
  }
  model: string
  modelBenchmark: { name: string; value: number; notice: string }
  elapsedSeconds: number
  preprocessing: string
  stats: Record<string, { pixels: number; percentage: number; color: string }>
  metrics: RecognitionMetrics
  preview: { original: string; overlay: string }
  warnings: string[]
}

export interface SimulationParameters {
  scaleMmPerPixel: number
  floorAreaM2?: number | null
  floors: number
  floorHeight: number
  city: string
  buildingType: string
  orientation: string
  heatingSystem: string
  coolingSystem: string
  wallU: number
  windowU: number
  roofU: number
  floorU: number
  windowShgc: number
  lightingPowerDensity: number
  equipmentPowerDensity: number
  operatingHours: number
  ventilationRate: number
}

export interface BimCadSimulation {
  simulationId: string
  method: string
  inputs: Record<string, unknown>
  result: {
    summary: {
      total_energy_kwh: number
      eui: number
      rating: string
      rating_label: string
      total_floor_area_m2: number
    }
    breakdown_kwh: Record<string, number>
    breakdown_eui: Record<string, number>
    geometry_used: Record<string, number>
    climate: { city: string; zone: string; hdd18: number; cdd26: number }
    systems: { heating: string; cooling: string }
  }
  warnings: string[]
}

export function getBimCadStatus() {
  return request<BimCadStatus>('/api/experiments/bim-cad/status')
}

export function recognizeBimCad(file: File, preprocessing = 'auto') {
  const body = new FormData()
  body.append('file', file)
  body.append('preprocessing', preprocessing)
  return request<BimCadRecognition>('/api/experiments/bim-cad/recognize', {
    method: 'POST',
    body,
  })
}

export function simulateBimCad(recognition: BimCadRecognition, parameters: SimulationParameters) {
  return request<BimCadSimulation>('/api/experiments/bim-cad/simulate', {
    method: 'POST',
    body: JSON.stringify({
      recognitionId: recognition.recognitionId,
      metrics: recognition.metrics,
      imageSize: {
        width: recognition.source.processedWidth,
        height: recognition.source.processedHeight,
      },
      parameters,
    }),
  })
}


