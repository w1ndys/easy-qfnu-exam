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
})
