import { afterEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'

const { readCurrentDatasetMock } = vi.hoisted(() => ({
  readCurrentDatasetMock: vi.fn(),
}))

vi.mock('@/lib/exams/store', () => ({
  getRedisClient: () => ({}),
  readCurrentDataset: readCurrentDatasetMock,
}))

const record = {
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
}

const dataset = {
  source: 'local-cron',
  semester: '2025-2026-2',
  generatedAt: '2026-06-26T10:00:00+08:00',
  version: '20260626020110',
  uploadedAt: '2026-06-26T02:01:10.000Z',
  recordCount: 1,
  records: [record],
}

describe('GET /api/exams/search', () => {
  afterEach(() => {
    readCurrentDatasetMock.mockReset()
  })

  it('returns empty results when no dataset exists', async () => {
    readCurrentDatasetMock.mockResolvedValue(null)
    const { GET } = await import('@/app/api/exams/search/route')
    const response = await GET(new NextRequest('http://localhost/api/exams/search'))
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body).toEqual({ meta: null, results: [] })
  })

  it('rejects invalid week params', async () => {
    const { GET } = await import('@/app/api/exams/search/route')
    const response = await GET(new NextRequest('http://localhost/api/exams/search?week=x'))

    expect(response.status).toBe(400)
  })

  it('treats empty filter params as missing', async () => {
    readCurrentDatasetMock.mockResolvedValue(null)
    const { GET } = await import('@/app/api/exams/search/route')
    const response = await GET(new NextRequest('http://localhost/api/exams/search?week=&weekday=&timeSlot='))
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body).toEqual({ meta: null, results: [] })
  })

  it('accepts week values greater than 30', async () => {
    readCurrentDatasetMock.mockResolvedValue(null)
    const { GET } = await import('@/app/api/exams/search/route')
    const response = await GET(new NextRequest('http://localhost/api/exams/search?week=31'))

    expect(response.status).toBe(200)
  })

  it('rejects weekday params outside 1 through 7', async () => {
    const { GET } = await import('@/app/api/exams/search/route')
    const response = await GET(new NextRequest('http://localhost/api/exams/search?weekday=8'))

    expect(response.status).toBe(400)
  })

  it('rejects non-decimal limit params', async () => {
    const { GET } = await import('@/app/api/exams/search/route')
    const response = await GET(new NextRequest('http://localhost/api/exams/search?limit=1e2'))

    expect(response.status).toBe(400)
  })

  it('uses the default limit when limit is empty', async () => {
    readCurrentDatasetMock.mockResolvedValue({
      ...dataset,
      recordCount: 150,
      records: Array.from({ length: 150 }, (_, index) => ({
        ...record,
        classroomId: String(index),
      })),
    })
    const { GET } = await import('@/app/api/exams/search/route')
    const response = await GET(new NextRequest('http://localhost/api/exams/search?limit='))
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.results).toHaveLength(100)
  })

  it('rejects reversed timeSlot ranges', async () => {
    const { GET } = await import('@/app/api/exams/search/route')
    const response = await GET(new NextRequest('http://localhost/api/exams/search?timeSlot=2-1'))

    expect(response.status).toBe(400)
  })

  it('returns meta and results for valid searches', async () => {
    readCurrentDatasetMock.mockResolvedValue(dataset)
    const { GET } = await import('@/app/api/exams/search/route')
    const response = await GET(new NextRequest('http://localhost/api/exams/search?week=19&weekday=1&limit=1000&timeSlot=1-2'))
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body).toEqual({
      meta: {
        semester: dataset.semester,
        generatedAt: dataset.generatedAt,
        uploadedAt: dataset.uploadedAt,
        recordCount: dataset.recordCount,
      },
      results: [record],
    })
  })

  it('returns 500 when Redis read fails', async () => {
    readCurrentDatasetMock.mockRejectedValue(new Error('redis unavailable'))
    const { GET } = await import('@/app/api/exams/search/route')
    const response = await GET(new NextRequest('http://localhost/api/exams/search'))

    expect(response.status).toBe(500)
  })
})
