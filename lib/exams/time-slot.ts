const INVALID_TIME_SLOT = '__invalid_time_slot__'

function invalidTimeSlot() {
  return [INVALID_TIME_SLOT]
}

function stripLeadingZero(value: string) {
  return String(Number(value))
}

export function normalizeTimeSlot(value: string): string[] {
  const trimmed = value.trim()

  if (!trimmed) {
    return []
  }

  if (trimmed.includes(',')) {
    const parts = trimmed.split(',').map((part) => part.trim())

    if (parts.some((part) => !/^\d+$/.test(part))) {
      return invalidTimeSlot()
    }

    return parts.map(stripLeadingZero)
  }

  if (trimmed.includes('-')) {
    const parts = trimmed.split('-').map((part) => part.trim())

    if (parts.length !== 2 || parts.some((part) => !/^\d+$/.test(part))) {
      return invalidTimeSlot()
    }

    const [startRaw, endRaw] = parts
    const start = Number(startRaw)
    const end = Number(endRaw)

    if (start > end) {
      return invalidTimeSlot()
    }

    return Array.from({ length: end - start + 1 }, (_, index) => String(start + index))
  }

  if (/^\d{4}$/.test(trimmed)) {
    return [stripLeadingZero(trimmed.slice(0, 2)), stripLeadingZero(trimmed.slice(2, 4))]
  }

  if (/^\d{2}$/.test(trimmed)) {
    return [stripLeadingZero(trimmed)]
  }

  if (/^\d+$/.test(trimmed)) {
    return [stripLeadingZero(trimmed)]
  }

  return invalidTimeSlot()
}
