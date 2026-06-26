import type { NextRequest } from 'next/server'
import { searchRecords } from '@/lib/exams/search'
import { getRedisClient, readCurrentDataset } from '@/lib/exams/store'
import { jsonError } from '@/lib/http/errors'

export const runtime = 'nodejs'

function parsePositiveLimit(value: string | null) {
  if (value === null) {
    return 100
  }

  if (!/^\d+$/.test(value)) {
    throw new Error('limit must be a positive integer')
  }

  const parsed = Number(value)

  if (parsed <= 0) {
    throw new Error('limit must be a positive integer')
  }

  return Math.min(parsed, 500)
}

function assertNumericParam(value: string | null, name: string, min: number, max: number) {
  if (value === null) {
    return
  }

  if (!/^\d+$/.test(value)) {
    throw new Error(`${name} must be numeric`)
  }

  const parsed = Number(value)

  if (parsed < min || parsed > max) {
    throw new Error(`${name} must be between ${min} and ${max}`)
  }
}

function assertValidTimeSlot(value: string | null) {
  if (value === null || value === '') {
    return
  }

  if (/^\d+$/.test(value) || /^\d+(,\d+)+$/.test(value)) {
    return
  }

  const range = value.match(/^(\d+)-(\d+)$/)

  if (!range) {
    throw new Error('timeSlot is invalid')
  }

  const start = Number(range[1])
  const end = Number(range[2])

  if (start > end || end - start + 1 > 4) {
    throw new Error('timeSlot is invalid')
  }
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams
  let limit = 100

  try {
    assertNumericParam(params.get('week'), 'week', 1, 30)
    assertNumericParam(params.get('weekday'), 'weekday', 1, 7)
    assertValidTimeSlot(params.get('timeSlot'))
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
