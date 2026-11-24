export interface TaskPrintContext {
  id: string; code: string; name: string; testPlan: string; version: number; canPrint: boolean
}
export interface TaskPrintJob {
  id: string; sourceId: string; sourceVersion: number; code: string
  submittedBy: { id: string; name: string }; createdAt: number; expiresAt: number
  status: 'queued' | 'running' | 'ready' | 'failed'; stage?: string; error?: string; historical: boolean
}
