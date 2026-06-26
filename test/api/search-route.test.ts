import { describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'

vi.mock('@/lib/exams/store', () => ({
  getRedisClient: () => ({}),
  readCurrentDataset: vi.fn(async () => null),
}))

describe('GET /api/exams/search', () => {
  it('returns empty results when no dataset exists', async () => {
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
})
