import { normalizeTimeSlot } from './time-slot'
import type { ExamRecord } from './types'

export type SearchFilters = {
  classroom?: string
  course?: string
  week?: string
  weekday?: string
  timeSlot?: string
  limit?: number
}

function includesNormalized(value: string, query: string) {
  return value.toLowerCase().includes(query.trim().toLowerCase())
}

function matchesTimeSlot(recordSlot: string, querySlot: string) {
  const recordParts = normalizeTimeSlot(recordSlot)
  const queryParts = normalizeTimeSlot(querySlot)

  if (queryParts.length === 0) {
    return true
  }

  if ([...queryParts, ...recordParts].some((part) => !/^\d+$/.test(part))) {
    return false
  }

  return queryParts.every((part) => recordParts.includes(part))
}

export function searchRecords(records: ExamRecord[], filters: SearchFilters): ExamRecord[] {
  const classroom = filters.classroom?.trim()
  const course = filters.course?.trim()
  const week = filters.week?.trim()
  const weekday = filters.weekday?.trim()
  const timeSlot = filters.timeSlot?.trim()
  const limit = filters.limit && filters.limit > 0 ? filters.limit : 100

  return records
    .filter((record) => {
      if (
        classroom &&
        !includesNormalized(record.classroomName, classroom) &&
        !includesNormalized(record.classroomId, classroom)
      ) {
        return false
      }

      if (course && !includesNormalized(record.courseName, course)) {
        return false
      }

      if (week && record.week !== week) {
        return false
      }

      if (weekday && record.weekday !== weekday) {
        return false
      }

      if (timeSlot && !matchesTimeSlot(record.timeSlot, timeSlot)) {
        return false
      }

      return true
    })
    .slice(0, limit)
}
