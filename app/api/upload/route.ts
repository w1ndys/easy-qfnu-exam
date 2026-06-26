import { parseUploadPayload } from '@/lib/exams/types'
import { getRedisClient, writeDataset } from '@/lib/exams/store'
import { jsonError } from '@/lib/http/errors'

export const runtime = 'nodejs'

function isAuthorized(request: Request) {
  const secret = process.env.UPLOAD_SECRET
  const authorization = request.headers.get('authorization')

  return Boolean(secret && authorization === `Bearer ${secret}`)
}

export async function POST(request: Request) {
  if (!isAuthorized(request)) {
    return jsonError('invalid upload secret', 401)
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
