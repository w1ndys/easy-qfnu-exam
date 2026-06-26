import { describe, expect, it } from 'vitest'
import { searchRecords } from '@/lib/exams/search'
import type { ExamRecord } from '@/lib/exams/types'

const records: ExamRecord[] = [
  {
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
  },
  {
    classroomName: 'JA102',
    classroomId: '2081',
    examStatus: '考试',
    courseName: '线性代数',
    examTime: '2026-07-07 10:30~2026-07-07 12:30',
    weekInfo: '19-203,204',
    weekday: '2',
    timeSlot: '0304',
    startTime: '10:10',
    endTime: '12:00',
    invigilator: '',
    week: '19',
  },
]

describe('searchRecords', () => {
  it('filters by classroom name substring', () => {
    expect(searchRecords(records, { classroom: 'JA101' })).toHaveLength(1)
  })

  it('filters by classroom ID substring', () => {
    expect(searchRecords(records, { classroom: '2081' })[0].classroomName).toBe('JA102')
  })

  it('filters by course substring', () => {
    expect(searchRecords(records, { course: '英语' })[0].courseName).toContain('英语')
  })

  it('filters by week weekday and normalized time slot', () => {
    const result = searchRecords(records, { week: '19', weekday: '1', timeSlot: '1-2' })
    expect(result).toHaveLength(1)
    expect(result[0].classroomName).toBe('JA101')
  })

  it('honors limit', () => {
    expect(searchRecords(records, { limit: 1 })).toHaveLength(1)
  })

  it('does not broaden results for invalid time slots', () => {
    expect(searchRecords(records, { timeSlot: '2-1' })).toHaveLength(0)
  })
})
