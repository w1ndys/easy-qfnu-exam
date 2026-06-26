import { describe, expect, it } from 'vitest'
import { normalizeTimeSlot } from '@/lib/exams/time-slot'

describe('normalizeTimeSlot', () => {
  it('normalizes compact slot strings', () => {
    expect(normalizeTimeSlot('0102')).toEqual(['1', '2'])
  })

  it('normalizes comma separated slot strings', () => {
    expect(normalizeTimeSlot('1,2')).toEqual(['1', '2'])
  })

  it('normalizes range slot strings', () => {
    expect(normalizeTimeSlot('1-2')).toEqual(['1', '2'])
  })

  it('normalizes mixed whitespace', () => {
    expect(normalizeTimeSlot(' 03, 04 ')).toEqual(['3', '4'])
  })

  it('returns no slots for blank input', () => {
    expect(normalizeTimeSlot('   ')).toEqual([])
  })

  it('normalizes invalid nonblank expressions to a non-matching marker', () => {
    expect(normalizeTimeSlot('2-1')).toEqual(['__invalid_time_slot__'])
    expect(normalizeTimeSlot('1-')).toEqual(['__invalid_time_slot__'])
    expect(normalizeTimeSlot('1-2-3')).toEqual(['__invalid_time_slot__'])
    expect(normalizeTimeSlot('1,,2')).toEqual(['__invalid_time_slot__'])
    expect(normalizeTimeSlot('1,a')).toEqual(['__invalid_time_slot__'])
  })
})
