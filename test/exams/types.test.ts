import { describe, expect, it } from 'vitest'
import { parseUploadPayload } from '@/lib/exams/types'

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

describe('parseUploadPayload', () => {
  it('accepts a valid upload payload', () => {
    const parsed = parseUploadPayload({
      source: 'local-cron',
      semester: '2025-2026-2',
      generatedAt: '2026-06-26T10:00:00+08:00',
      records: [record],
    })

    expect(parsed.records).toHaveLength(1)
    expect(parsed.records[0].courseName).toBe('大学英语2（普通）')
  })

  it('accepts empty records', () => {
    const parsed = parseUploadPayload({
      source: 'local-cron',
      semester: '2025-2026-2',
      generatedAt: '2026-06-26T10:00:00+08:00',
      records: [],
    })

    expect(parsed.records).toEqual([])
  })

  it('rejects missing records', () => {
    expect(() => parseUploadPayload({
      source: 'local-cron',
      semester: '2025-2026-2',
      generatedAt: '2026-06-26T10:00:00+08:00',
    })).toThrow('records must be an array')
  })

  it('rejects records with missing fields', () => {
    const invalid = { ...record }
    delete (invalid as Partial<typeof record>).courseName

    expect(() => parseUploadPayload({
      source: 'local-cron',
      semester: '2025-2026-2',
      generatedAt: '2026-06-26T10:00:00+08:00',
      records: [invalid],
    })).toThrow('records[0].courseName must be a string')
  })
})
