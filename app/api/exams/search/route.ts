import type { NextRequest } from 'next/server'
import { searchRecords } from '@/lib/exams/search'
import { getRedisClient, readCurrentDataset } from '@/lib/exams/store'
import { jsonError } from '@/lib/http/errors'

export const runtime = 'nodejs'

function parsePositiveLimit(value: string | null) {
  if (!value) {
    return 100
  }

  const parsed = Number(value)

  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error('limit must be a positive integer')
  }

  return Math.min(parsed, 500)
}

function assertNumericParam(value: string | null, name: string) {
  if (value && !/^\d+$/.test(value)) {
    throw new Error(`${name} must be numeric`)
  }
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams
  let limit = 100

  try {
    assertNumericParam(params.get('week'), 'week')
    assertNumericParam(params.get('weekday'), 'weekday')
    limit = parsePositiveLimit(params.get('limit'))
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : 'invalid query params', 400)
  }

  try {
    const dataset = await readCurrentDataset(getRedisClient())

    if (!dataset) {
      return Response.json({ meta: null, results: [] })
    }

    const results = searchRecords(dataset.records, {
      classroom: params.get('classroom') ?? undefined,
      course: params.get('course') ?? undefined,
      week: params.get('week') ?? undefined,
      weekday: params.get('weekday') ?? undefined,
      timeSlot: params.get('timeSlot') ?? undefined,
      limit,
    })

    return Response.json({
      meta: {
        semester: dataset.semester,
        generatedAt: dataset.generatedAt,
        uploadedAt: dataset.uploadedAt,
        recordCount: dataset.recordCount,
      },
      results,
    })
  } catch {
    return jsonError('failed to query dataset', 500)
  }
}
