export type SampleStatus = 'pending' | 'received' | 'returned'
export type SampleAction = 'created' | 'edited' | 'received' | 'returned' | 'resubmitted'
export interface SampleEvent { id: string; action: SampleAction; actor: string; at: string; reason?: string }
export interface SampleInput {
  name: string; category: string; customer: string; contact: string; phone: string;
  quantity: number; unit: string; projects: string[]; storage: string; notes: string
}
export interface Sample extends SampleInput { id: string; code: string; status: SampleStatus; createdAt: string; updatedAt: string; events: SampleEvent[]; customerId?: string; projectIds?: string[]; version?: number }
export interface SampleQuery { keyword?: string; customer?: string; status?: SampleStatus | ''; from?: string; to?: string; page?: number; pageSize?: number }
