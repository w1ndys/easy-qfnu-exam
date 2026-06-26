function stripLeadingZero(value: string) {
  return String(Number(value))
}

export function normalizeTimeSlot(value: string): string[] {
  const trimmed = value.trim()

  if (!trimmed) {
    return []
  }

  if (trimmed.includes(',')) {
    return trimmed.split(',').map((part) => stripLeadingZero(part.trim())).filter(Boolean)
  }

  if (trimmed.includes('-')) {
    const [startRaw, endRaw] = trimmed.split('-')
    const start = Number(startRaw.trim())
    const end = Number(endRaw.trim())

    if (!Number.isInteger(start) || !Number.isInteger(end) || start > end) {
      return []
    }

    return Array.from({ length: end - start + 1 }, (_, index) => String(start + index))
  }

  if (/^\d{4}$/.test(trimmed)) {
    return [stripLeadingZero(trimmed.slice(0, 2)), stripLeadingZero(trimmed.slice(2, 4))]
  }

  if (/^\d{2}$/.test(trimmed)) {
    return [stripLeadingZero(trimmed)]
  }

  return [trimmed]
}
