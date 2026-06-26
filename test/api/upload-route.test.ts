import { afterEach, describe, expect, it, vi } from 'vitest'

const { writeDatasetMock } = vi.hoisted(() => ({
  writeDatasetMock: vi.fn(),
}))

vi.mock('@/lib/exams/store', () => ({
  getRedisClient: () => ({}),
  writeDataset: writeDatasetMock,
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
    writeDatasetMock.mockReset()
  })

  function authorize() {
    process.env.UPLOAD_SECRET = 'secret'
  }

  function makeRequest(body: BodyInit, headers: HeadersInit = {}) {
    return new Request('http://localhost/api/upload', {
      method: 'POST',
      headers: { authorization: 'Bearer secret', ...headers },
      body,
    })
  }

  function mockSuccessfulWrite() {
    writeDatasetMock.mockResolvedValue({
      version: '20260626020110',
      recordCount: 1,
      uploadedAt: '2026-06-26T02:01:10.000Z',
    })
  }

  it('rejects requests without a valid secret', async () => {
    authorize()
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
    authorize()
    mockSuccessfulWrite()
    const { POST } = await import('@/app/api/upload/route')

    const response = await POST(makeRequest(JSON.stringify(validPayload)))
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.recordCount).toBe(1)
  })

  it('rejects invalid JSON bodies', async () => {
    authorize()
    const { POST } = await import('@/app/api/upload/route')

    const response = await POST(makeRequest('{'))

    expect(response.status).toBe(400)
  })

  it('rejects empty records payloads', async () => {
    authorize()
    const { POST } = await import('@/app/api/upload/route')

    const response = await POST(makeRequest(JSON.stringify({ ...validPayload, records: [] })))

    expect(response.status).toBe(400)
  })

  it('rejects content-length greater than one megabyte', async () => {
    authorize()
    const { POST } = await import('@/app/api/upload/route')

    const response = await POST(makeRequest(JSON.stringify(validPayload), { 'content-length': '1000001' }))
    const body = await response.json()

    expect(response.status).toBe(413)
    expect(body.error).toBe('payload too large')
  })

  it('rejects more than 5000 records', async () => {
    authorize()
    const { POST } = await import('@/app/api/upload/route')
    const payload = { ...validPayload, records: Array.from({ length: 5001 }, () => validPayload.records[0]) }

    const response = await POST(makeRequest(JSON.stringify(payload)))
    const body = await response.json()

    expect(response.status).toBe(413)
    expect(body.error).toBe('too many records')
  })

  it('rejects string fields longer than 500 characters with the field path', async () => {
    authorize()
    const { POST } = await import('@/app/api/upload/route')
    const payload = {
      ...validPayload,
      records: [{ ...validPayload.records[0], courseName: 'x'.repeat(501) }],
    }

    const response = await POST(makeRequest(JSON.stringify(payload)))
    const body = await response.json()

    expect(response.status).toBe(400)
    expect(body.error).toContain('records[0].courseName')
  })

  it('returns 500 when Redis write fails', async () => {
    authorize()
    writeDatasetMock.mockRejectedValue(new Error('redis unavailable'))
    const { POST } = await import('@/app/api/upload/route')

    const response = await POST(makeRequest(JSON.stringify(validPayload)))

    expect(response.status).toBe(500)
  })
})
