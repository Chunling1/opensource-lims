import {beforeEach, expect, it, vi} from 'vitest'
const mocks = vi.hoisted(() => ({request: vi.fn()}))
vi.mock('@/services/http', () => ({request: mocks.request, authedFetch: vi.fn()}))
vi.mock('@/services/auth', () => ({USE_BACKEND: true}))
import {listUploadedAttachments} from '@/services/attachments'

beforeEach(() => mocks.request.mockReset())
it('all consumers receive only uploaded files even when a legacy cover was selected', async () => {
  const rows = [
    {id: 1, name: '系统生成封面.docx', source: '模板生成', selectedForOfficial: true},
    {id: 2, name: '系统生成封面.pdf', source: '模板生成'},
    {id: 3, name: '系统生成封面.docx', source: '其他附件'},
    {id: 4, name: '完整报告.docx', source: '完整报告正文'},
    {id: 5, name: '原始记录.pdf', source: '原始记录'},
  ]
  mocks.request.mockResolvedValue({rows})
  expect((await listUploadedAttachments('TEST-R', 'query')).map(file => file.id)).toEqual([3, 4, 5])
  expect(rows).toHaveLength(5)
})
