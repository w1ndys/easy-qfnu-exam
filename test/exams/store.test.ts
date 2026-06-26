import { describe, expect, it } from 'vitest'
import { readCurrentDataset, writeDataset } from '@/lib/exams/store'
import type { UploadPayload } from '@/lib/exams/types'

class FakeRedis {
  values = new Map<string, unknown>()
  writes: string[] = []

  async get<T>(key: string): Promise<T | null> {
    return (this.values.get(key) as T | undefined) ?? null
  }

  async set(key: string, value: unknown): Promise<'OK'> {
    this.values.set(key, value)
    this.writes.push(key)
    return 'OK'
  }
}

const payload: UploadPayload = {
  source: 'local-cron',
  semester: '2025-2026-2',
  generatedAt: '2026-06-26T10:00:00+08:00',
  records: [{
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
  }],
}

describe('exam dataset store', () => {
  it('writes version key before current key', async () => {
    const redis = new FakeRedis()
    const dataset = await writeDataset(redis, payload, new Date('2026-06-26T02:01:10.000Z'))

    expect(dataset.recordCount).toBe(1)
    expect(redis.writes[0]).toMatch(/^exam:version:/)
    expect(redis.writes[1]).toBe('exam:current')
  })

  it('reads current dataset', async () => {
    const redis = new FakeRedis()
    const written = await writeDataset(redis, payload, new Date('2026-06-26T02:01:10.000Z'))

    await expect(readCurrentDataset(redis)).resolves.toEqual(written)
  })
})
