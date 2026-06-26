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
  return date.toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)
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
  return redis.get<ExamDataset>(CURRENT_DATASET_KEY)
}
