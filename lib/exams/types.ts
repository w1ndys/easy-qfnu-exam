export type ExamRecord = {
  classroomName: string
  classroomId: string
  examStatus: string
  courseName: string
  examTime: string
  weekInfo: string
  weekday: string
  timeSlot: string
  startTime: string
  endTime: string
  invigilator: string
  week: string
}

export type UploadPayload = {
  source: string
  semester: string
  generatedAt: string
  records: ExamRecord[]
}

export type ExamDataset = UploadPayload & {
  version: string
  uploadedAt: string
  recordCount: number
}

const recordFields: Array<keyof ExamRecord> = [
  'classroomName',
  'classroomId',
  'examStatus',
  'courseName',
  'examTime',
  'weekInfo',
  'weekday',
  'timeSlot',
  'startTime',
  'endTime',
  'invigilator',
  'week',
]

function assertString(value: unknown, path: string): asserts value is string {
  if (typeof value !== 'string') {
    throw new Error(`${path} must be a string`)
  }
}

function parseRecord(value: unknown, index: number): ExamRecord {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`records[${index}] must be an object`)
  }

  const input = value as Record<string, unknown>
  const record = {} as ExamRecord

  for (const field of recordFields) {
    assertString(input[field], `records[${index}].${field}`)
    record[field] = input[field]
  }

  return record
}

export function parseUploadPayload(value: unknown): UploadPayload {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('payload must be an object')
  }

  const input = value as Record<string, unknown>
  assertString(input.source, 'source')
  assertString(input.semester, 'semester')
  assertString(input.generatedAt, 'generatedAt')

  if (!Array.isArray(input.records)) {
    throw new Error('records must be an array')
  }

  if (input.records.length === 0) {
    throw new Error('records must not be empty')
  }

  return {
    source: input.source,
    semester: input.semester,
    generatedAt: input.generatedAt,
    records: input.records.map(parseRecord),
  }
}
