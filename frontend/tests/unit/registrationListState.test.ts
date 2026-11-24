import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Actor } from '../../src/types/lims'
vi.mock('../../src/stores/session', async () => { const { shallowRef } = await import('vue'); return { currentActor: shallowRef<Actor>({ id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }) } })
import { currentActor } from '../../src/stores/session'
import { clearRegistrationListState, restoreRegistrationListState, saveRegistrationListState, takeRegistrationReturnScroll, type RegistrationListState } from '../../src/services/commissions/registrationListState'

const url = '/commissions/registration?current=c1&cPage=2'
function store() {
  saveRegistrationListState({ url, commissions: { items: [{ id: 'c1', version: 1 }], page: 2, pageSize: 5, total: 6 },
    samples: { items: [{ id: 's1', version: 1 }], page: 1, pageSize: 10, total: 1 }, current: { id: 'c1', version: 1 },
    selectedSamples: ['s1'], scroll: { left: 0, top: 360 } } as RegistrationListState)
}
beforeEach(() => { clearRegistrationListState(); currentActor.value = { id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }; store() })
describe('registration list return state', () => {
  it('restores matching queries once, including saved sample return markers and scroll', () => {
    const target = '/commissions/registration?cPage=2&savedSample=s1&current=c1'
    expect(restoreRegistrationListState(target)?.selectedSamples).toEqual(['s1'])
    expect(takeRegistrationReturnScroll(target)).toEqual({ left: 0, top: 360 })
    expect(takeRegistrationReturnScroll(target)).toBeUndefined()
    expect(restoreRegistrationListState(target)).toBeUndefined()
    store(); expect(restoreRegistrationListState('/commissions/registration?cPage=1')).toBeUndefined()
  })
  it('discards summaries when identity or permission scope changes, including switching back', () => {
    currentActor.value = { ...currentActor.value, scope: 'department' }
    currentActor.value = { ...currentActor.value, scope: 'all' }
    expect(restoreRegistrationListState(url)).toBeUndefined()
  })
})
