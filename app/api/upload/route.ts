import { parseUploadPayload, type ExamRecord, type UploadPayload } from '@/lib/exams/types'
import { getRedisClient, writeDataset } from '@/lib/exams/store'
import { jsonError } from '@/lib/http/errors'

export const runtime = 'nodejs'

const MAX_CONTENT_LENGTH = 1_000_000
const MAX_RECORDS = 5000
const MAX_STRING_LENGTH = 500

const recordFields: Array<keyof ExamRecord> = [
  'classroomName',
  'classroomId',
  'examStatus',
  'courseName',
  'examTime',
  'weekInfo',
  'weekday',
  'timeSlot',
  'startTime',
  'endTime',
  'invigilator',
  'week',
]

function isAuthorized(request: Request) {
  const secret = process.env.UPLOAD_SECRET
  const authorization = request.headers.get('authorization')

  return Boolean(secret && authorization === `Bearer ${secret}`)
}

function isPayloadTooLarge(request: Request) {
  const contentLength = request.headers.get('content-length')

  return Boolean(contentLength && Number(contentLength) > MAX_CONTENT_LENGTH)
}

function assertStringLength(value: string, path: string) {
  if (value.length > MAX_STRING_LENGTH) {
    throw new Error(`${path} is too long`)
  }
}

function assertPayloadLimits(payload: UploadPayload) {
  if (payload.records.length > MAX_RECORDS) {
    return jsonError('too many records', 413)
  }

  try {
    assertStringLength(payload.source, 'source')
    assertStringLength(payload.semester, 'semester')
    assertStringLength(payload.generatedAt, 'generatedAt')

    payload.records.forEach((record, index) => {
      for (const field of recordFields) {
        assertStringLength(record[field], `records[${index}].${field}`)
      }
    })
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : 'invalid payload', 400)
  }

  return null
}

export async function POST(request: Request) {
  if (!isAuthorized(request)) {
    return jsonError('invalid upload secret', 401)
  }

  if (isPayloadTooLarge(request)) {
    return jsonError('payload too large', 413)
  }

  let body: unknown

  try {
    body = await request.json()
  } catch {
    return jsonError('invalid json body', 400)
  }

  let payload

  try {
    payload = parseUploadPayload(body)
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : 'invalid payload', 400)
  }

  const limitError = assertPayloadLimits(payload)

  if (limitError) {
    return limitError
  }

  try {
    const dataset = await writeDataset(getRedisClient(), payload)

    return Response.json({
      ok: true,
      version: dataset.version,
      recordCount: dataset.recordCount,
      uploadedAt: dataset.uploadedAt,
    })
  } catch {
    return jsonError('failed to write dataset', 500)
  }
}
