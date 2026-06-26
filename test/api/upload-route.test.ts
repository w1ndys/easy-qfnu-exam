import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/exams/store', () => ({
  getRedisClient: () => ({}),
  writeDataset: vi.fn(async () => ({
    version: '20260626020110',
    recordCount: 1,
    uploadedAt: '2026-06-26T02:01:10.000Z',
  })),
}))

const validPayload = {
  source: 'local-cron',
  semester: '2025-2026-2',
  generatedAt: '2026-06-26T10:00:00+08:00',
  records: [
    {
      classroomName: 'JA101',
      classroomId: '2080',
      examStatus: '考试',
      courseName: '大学英语2（普通）',
      examTime: '2026-07-06 08:00~2026-07-06 10:00',
      weekInfo: '19-101,102',
      weekday: '1',
      timeSlot: '0102',
      startTime: '8:00',
      endTime: '9:50',
      invigilator: '',
      week: '19',
    },
  ],
}

describe('POST /api/upload', () => {
  afterEach(() => {
    delete process.env.UPLOAD_SECRET
  })

  it('rejects requests without a valid secret', async () => {
    process.env.UPLOAD_SECRET = 'secret'
    const { POST } = await import('@/app/api/upload/route')

    const response = await POST(
      new Request('http://localhost/api/upload', {
        method: 'POST',
        body: JSON.stringify(validPayload),
      }),
    )

    expect(response.status).toBe(401)
  })

  it('accepts valid payloads with a valid secret', async () => {
    process.env.UPLOAD_SECRET = 'secret'
    const { POST } = await import('@/app/api/upload/route')

    const response = await POST(
      new Request('http://localhost/api/upload', {
        method: 'POST',
        headers: { authorization: 'Bearer secret' },
        body: JSON.stringify(validPayload),
      }),
    )
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.recordCount).toBe(1)
  })
})
