import { randomUUID } from 'node:crypto'
import { Redis } from '@upstash/redis'
import type { ExamDataset, UploadPayload } from './types'

export type RedisLike = {
  get<T>(key: string): Promise<T | null>
  set(key: string, value: unknown): Promise<unknown>
}

export const CURRENT_DATASET_KEY = 'exam:current'

export function getRedisClient(): RedisLike {
  return Redis.fromEnv()
}

function makeVersion(date: Date) {
  const timestamp = date.toISOString().replace(/[-:TZ.]/g, '').slice(0, 17)
  const suffix = randomUUID().replace(/-/g, '').slice(0, 8)

  return `${timestamp}-${suffix}`
}

function isExamDataset(value: unknown): value is ExamDataset {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false
  }

  const input = value as Record<string, unknown>

  return (
    typeof input.version === 'string' &&
    typeof input.uploadedAt === 'string' &&
    typeof input.recordCount === 'number' &&
    Array.isArray(input.records)
  )
}

export async function writeDataset(redis: RedisLike, payload: UploadPayload, now = new Date()): Promise<ExamDataset> {
  const version = makeVersion(now)
  const dataset: ExamDataset = {
    ...payload,
    version,
    uploadedAt: now.toISOString(),
    recordCount: payload.records.length,
  }

  await redis.set(`exam:version:${version}`, dataset)
  await redis.set(CURRENT_DATASET_KEY, dataset)

  return dataset
}

export async function readCurrentDataset(redis: RedisLike): Promise<ExamDataset | null> {
  const dataset = await redis.get<unknown>(CURRENT_DATASET_KEY)

  if (!isExamDataset(dataset)) {
    return null
  }

  return dataset
}
