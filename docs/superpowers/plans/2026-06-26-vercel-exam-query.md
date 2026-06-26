# Vercel Exam Query Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a public Next.js exam query site on Vercel with a protected JSON upload API and Redis-backed current exam dataset storage.

**Architecture:** The local crawler remains responsible for logging in to the academic system and generating exam records. The Next.js app stores the latest uploaded dataset in Redis using a versioned key pattern, exposes a protected upload route, exposes a public search route, and renders a public query page with visible update metadata. Vercel KV is deprecated for new projects, so implement the KV semantics with Vercel Marketplace Upstash Redis and `@upstash/redis`.

**Tech Stack:** Next.js App Router, React, TypeScript, `@upstash/redis`, Vitest, Python `requests`.

---

## File Structure

Create and modify these files:

```text
package.json                              Node scripts and dependencies.
next.config.ts                            Minimal Next.js config.
tsconfig.json                             TypeScript config.
vitest.config.ts                          Vitest config for pure TypeScript tests.
app/layout.tsx                            App shell and metadata.
app/page.tsx                              Public query page.
app/globals.css                           Page styling.
app/api/upload/route.ts                   Protected upload route.
app/api/exams/search/route.ts             Public search route.
lib/exams/types.ts                        Shared exam dataset types and validators.
lib/exams/time-slot.ts                    Time-slot normalization utilities.
lib/exams/search.ts                       Pure search/filtering logic.
lib/exams/store.ts                        Redis read/write functions.
lib/http/errors.ts                        JSON error helpers for route handlers.
test/exams/time-slot.test.ts              Unit tests for time-slot normalization.
test/exams/search.test.ts                 Unit tests for filtering.
test/exams/types.test.ts                  Unit tests for payload validation.
test/exams/store.test.ts                  Unit tests for Redis key write order using a fake client.
test/api/upload-route.test.ts             Unit tests for upload route auth and validation.
test/api/search-route.test.ts             Unit tests for search route empty dataset and invalid params.
crawl_exams.py                            Add UTF-8 JSON payload output and optional upload mode.
```

Do not add academic-system login logic to Vercel. Do not commit secrets. Required production environment variables are `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, and `UPLOAD_SECRET`.

## Task 1: Scaffold Next.js App

**Files:**
- Create: `package.json`
- Create: `next.config.ts`
- Create: `tsconfig.json`
- Create: `vitest.config.ts`
- Create: `app/layout.tsx`
- Create: `app/globals.css`
- Create: `app/page.tsx`

- [ ] **Step 1: Create package and config files**

Create `package.json`:

```json
{
  "name": "easy-qfnu-exam",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@upstash/redis": "latest",
    "next": "latest",
    "react": "latest",
    "react-dom": "latest"
  },
  "devDependencies": {
    "@types/node": "latest",
    "@types/react": "latest",
    "@types/react-dom": "latest",
    "typescript": "latest",
    "vitest": "latest"
  }
}
```

Create `next.config.ts`:

```ts
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {}

export default nextConfig
```

Create `tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "ES2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

Create `vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    include: ['test/**/*.test.ts'],
  },
})
```

- [ ] **Step 2: Create minimal app shell**

Create `app/layout.tsx`:

```tsx
import './globals.css'
import type { Metadata } from 'next'
import type { ReactNode } from 'react'

export const metadata: Metadata = {
  title: 'QFNU 考试安排查询',
  description: '曲阜师范大学考试安排自助查询',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
```

Create `app/globals.css`:

```css
:root {
  color: #172033;
  background: #f6f8fc;
  font-family: Arial, 'Microsoft YaHei', sans-serif;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}

button,
input,
select {
  font: inherit;
}
```

Create `app/page.tsx`:

```tsx
export default function HomePage() {
  return (
    <main className="page-shell">
      <h1>QFNU 考试安排查询</h1>
      <p>请输入教室、科目、周次、星期或节次查询考试记录。</p>
    </main>
  )
}
```

- [ ] **Step 3: Install dependencies**

Run: `npm install`

Expected: dependencies install and `package-lock.json` is created.

- [ ] **Step 4: Verify scaffold**

Run: `npm run typecheck`

Expected: TypeScript exits with status 0.

Run: `npm run build`

Expected: Next.js build exits with status 0.

- [ ] **Step 5: Commit scaffold**

Run:

```bash
git add package.json package-lock.json next.config.ts tsconfig.json vitest.config.ts app/layout.tsx app/globals.css app/page.tsx
git commit -m "feat(next): 初始化考试查询站点"
```

## Task 2: Define Exam Types and Time-Slot Normalization

**Files:**
- Create: `lib/exams/types.ts`
- Create: `lib/exams/time-slot.ts`
- Create: `test/exams/types.test.ts`
- Create: `test/exams/time-slot.test.ts`

- [ ] **Step 1: Write failing tests for validators and time slots**

Create `test/exams/types.test.ts`:

```ts
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

  it('rejects empty records', () => {
    expect(() => parseUploadPayload({
      source: 'local-cron',
      semester: '2025-2026-2',
      generatedAt: '2026-06-26T10:00:00+08:00',
      records: [],
    })).toThrow('records must not be empty')
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
```

Create `test/exams/time-slot.test.ts`:

```ts
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- test/exams/types.test.ts test/exams/time-slot.test.ts`

Expected: FAIL because `@/lib/exams/types` and `@/lib/exams/time-slot` do not exist.

- [ ] **Step 3: Implement types and normalizer**

Create `lib/exams/types.ts`:

```ts
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
```

Create `lib/exams/time-slot.ts`:

```ts
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- test/exams/types.test.ts test/exams/time-slot.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit types and normalization**

Run:

```bash
git add lib/exams/types.ts lib/exams/time-slot.ts test/exams/types.test.ts test/exams/time-slot.test.ts
git commit -m "feat(exams): 定义考试数据模型和节次归一化"
```

## Task 3: Implement Pure Search Logic

**Files:**
- Create: `lib/exams/search.ts`
- Create: `test/exams/search.test.ts`

- [ ] **Step 1: Write failing search tests**

Create `test/exams/search.test.ts`:

```ts
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
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- test/exams/search.test.ts`

Expected: FAIL because `@/lib/exams/search` does not exist.

- [ ] **Step 3: Implement search logic**

Create `lib/exams/search.ts`:

```ts
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

  return queryParts.every((part) => recordParts.includes(part))
}

export function searchRecords(records: ExamRecord[], filters: SearchFilters): ExamRecord[] {
  const classroom = filters.classroom?.trim()
  const course = filters.course?.trim()
  const week = filters.week?.trim()
  const weekday = filters.weekday?.trim()
  const timeSlot = filters.timeSlot?.trim()
  const limit = filters.limit && filters.limit > 0 ? filters.limit : 100

  return records.filter((record) => {
    if (classroom && !includesNormalized(record.classroomName, classroom) && !includesNormalized(record.classroomId, classroom)) {
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
  }).slice(0, limit)
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- test/exams/search.test.ts test/exams/time-slot.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit search logic**

Run:

```bash
git add lib/exams/search.ts test/exams/search.test.ts
git commit -m "feat(exams): 实现考试记录筛选逻辑"
```

## Task 4: Implement Redis Dataset Store

**Files:**
- Create: `lib/exams/store.ts`
- Create: `test/exams/store.test.ts`

- [ ] **Step 1: Write failing store tests with fake Redis**

Create `test/exams/store.test.ts`:

```ts
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- test/exams/store.test.ts`

Expected: FAIL because `@/lib/exams/store` does not exist.

- [ ] **Step 3: Implement Redis store**

Create `lib/exams/store.ts`:

```ts
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- test/exams/store.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit store**

Run:

```bash
git add lib/exams/store.ts test/exams/store.test.ts
git commit -m "feat(store): 添加考试数据Redis存储"
```

## Task 5: Implement Upload and Search Route Handlers

**Files:**
- Create: `lib/http/errors.ts`
- Create: `app/api/upload/route.ts`
- Create: `app/api/exams/search/route.ts`
- Create: `test/api/upload-route.test.ts`
- Create: `test/api/search-route.test.ts`

- [ ] **Step 1: Create route helper**

Create `lib/http/errors.ts`:

```ts
export function jsonError(message: string, status: number) {
  return Response.json({ ok: false, error: message }, { status })
}
```

- [ ] **Step 2: Implement protected upload route**

Create `app/api/upload/route.ts`:

```ts
import { parseUploadPayload } from '@/lib/exams/types'
import { getRedisClient, writeDataset } from '@/lib/exams/store'
import { jsonError } from '@/lib/http/errors'

export const runtime = 'nodejs'

function isAuthorized(request: Request) {
  const secret = process.env.UPLOAD_SECRET
  const authorization = request.headers.get('authorization')

  return Boolean(secret && authorization === `Bearer ${secret}`)
}

export async function POST(request: Request) {
  if (!isAuthorized(request)) {
    return jsonError('invalid upload secret', 401)
  }

  let body: unknown

  try {
    body = await request.json()
  } catch {
    return jsonError('invalid json body', 400)
  }

  let payload

  try {
    payload = parseUploadPayload(body)
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : 'invalid payload', 400)
  }

  try {
    const dataset = await writeDataset(getRedisClient(), payload)
    return Response.json({
      ok: true,
      version: dataset.version,
      recordCount: dataset.recordCount,
      uploadedAt: dataset.uploadedAt,
    })
  } catch {
    return jsonError('failed to write dataset', 500)
  }
}
```

- [ ] **Step 3: Implement public search route**

Create `app/api/exams/search/route.ts`:

```ts
import type { NextRequest } from 'next/server'
import { searchRecords } from '@/lib/exams/search'
import { getRedisClient, readCurrentDataset } from '@/lib/exams/store'
import { jsonError } from '@/lib/http/errors'

export const runtime = 'nodejs'

function parsePositiveLimit(value: string | null) {
  if (!value) {
    return 100
  }

  const parsed = Number(value)

  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error('limit must be a positive integer')
  }

  return Math.min(parsed, 500)
}

function assertNumericParam(value: string | null, name: string) {
  if (value && !/^\d+$/.test(value)) {
    throw new Error(`${name} must be numeric`)
  }
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams
  let limit = 100

  try {
    assertNumericParam(params.get('week'), 'week')
    assertNumericParam(params.get('weekday'), 'weekday')
    limit = parsePositiveLimit(params.get('limit'))
  } catch (error) {
    return jsonError(error instanceof Error ? error.message : 'invalid query params', 400)
  }

  try {
    const dataset = await readCurrentDataset(getRedisClient())

    if (!dataset) {
      return Response.json({ meta: null, results: [] })
    }

    const results = searchRecords(dataset.records, {
      classroom: params.get('classroom') ?? undefined,
      course: params.get('course') ?? undefined,
      week: params.get('week') ?? undefined,
      weekday: params.get('weekday') ?? undefined,
      timeSlot: params.get('timeSlot') ?? undefined,
      limit,
    })

    return Response.json({
      meta: {
        semester: dataset.semester,
        generatedAt: dataset.generatedAt,
        uploadedAt: dataset.uploadedAt,
        recordCount: dataset.recordCount,
      },
      results,
    })
  } catch {
    return jsonError('failed to query dataset', 500)
  }
}
```

- [ ] **Step 4: Add route behavior tests**

Create `test/api/upload-route.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/exams/store', () => ({
  getRedisClient: () => ({}),
  writeDataset: vi.fn(async () => ({
    version: '20260626020110',
    recordCount: 1,
    uploadedAt: '2026-06-26T02:01:10.000Z',
  })),
}))

const validPayload = {
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

describe('POST /api/upload', () => {
  afterEach(() => {
    delete process.env.UPLOAD_SECRET
  })

  it('rejects requests without a valid secret', async () => {
    process.env.UPLOAD_SECRET = 'secret'
    const { POST } = await import('@/app/api/upload/route')

    const response = await POST(new Request('http://localhost/api/upload', {
      method: 'POST',
      body: JSON.stringify(validPayload),
    }))

    expect(response.status).toBe(401)
  })

  it('accepts valid payloads with a valid secret', async () => {
    process.env.UPLOAD_SECRET = 'secret'
    const { POST } = await import('@/app/api/upload/route')

    const response = await POST(new Request('http://localhost/api/upload', {
      method: 'POST',
      headers: { authorization: 'Bearer secret' },
      body: JSON.stringify(validPayload),
    }))
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.recordCount).toBe(1)
  })
})
```

Create `test/api/search-route.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'

vi.mock('@/lib/exams/store', () => ({
  getRedisClient: () => ({}),
  readCurrentDataset: vi.fn(async () => null),
}))

describe('GET /api/exams/search', () => {
  it('returns empty results when no dataset exists', async () => {
    const { GET } = await import('@/app/api/exams/search/route')
    const response = await GET(new NextRequest('http://localhost/api/exams/search'))
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body).toEqual({ meta: null, results: [] })
  })

  it('rejects invalid week params', async () => {
    const { GET } = await import('@/app/api/exams/search/route')
    const response = await GET(new NextRequest('http://localhost/api/exams/search?week=x'))

    expect(response.status).toBe(400)
  })
})
```

- [ ] **Step 5: Verify typecheck and tests**

Run: `npm run typecheck`

Expected: PASS.

Run: `npm test`

Expected: PASS.

- [ ] **Step 6: Commit routes**

Run:

```bash
git add lib/http/errors.ts app/api/upload/route.ts app/api/exams/search/route.ts test/api/upload-route.test.ts test/api/search-route.test.ts
git commit -m "feat(api): 添加考试数据上传和查询接口"
```

## Task 6: Build Public Query Page

**Files:**
- Modify: `app/page.tsx`
- Modify: `app/globals.css`

- [ ] **Step 1: Replace page with client query UI**

Replace `app/page.tsx` with:

```tsx
'use client'

import { FormEvent, useState } from 'react'
import type { ExamRecord } from '@/lib/exams/types'

type SearchMeta = {
  semester: string
  generatedAt: string
  uploadedAt: string
  recordCount: number
} | null

type SearchResponse = {
  meta: SearchMeta
  results: ExamRecord[]
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

export default function HomePage() {
  const [classroom, setClassroom] = useState('')
  const [course, setCourse] = useState('')
  const [week, setWeek] = useState('')
  const [weekday, setWeekday] = useState('')
  const [timeSlot, setTimeSlot] = useState('')
  const [meta, setMeta] = useState<SearchMeta>(null)
  const [results, setResults] = useState<ExamRecord[]>([])
  const [message, setMessage] = useState('请输入条件后查询')
  const [loading, setLoading] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setMessage('查询中...')

    const params = new URLSearchParams()
    if (classroom.trim()) params.set('classroom', classroom.trim())
    if (course.trim()) params.set('course', course.trim())
    if (week.trim()) params.set('week', week.trim())
    if (weekday.trim()) params.set('weekday', weekday.trim())
    if (timeSlot.trim()) params.set('timeSlot', timeSlot.trim())

    try {
      const response = await fetch(`/api/exams/search?${params.toString()}`)
      if (!response.ok) {
        throw new Error(await response.text())
      }

      const data = (await response.json()) as SearchResponse
      setMeta(data.meta)
      setResults(data.results)

      if (!data.meta) {
        setMessage('暂无同步数据')
      } else if (data.results.length === 0) {
        setMessage('没有找到匹配的考试记录')
      } else {
        setMessage(`找到 ${data.results.length} 条记录`)
      }
    } catch {
      setMessage('查询失败，请稍后再试')
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">easy-qfnu-exam</p>
        <h1>QFNU 考试安排查询</h1>
        <p>按教室、科目、周次、星期和节次查询考试记录。</p>
        <div className="status-card">
          <span>当前学期：{meta?.semester ?? '暂无数据'}</span>
          <span>数据更新时间：{meta ? formatDateTime(meta.uploadedAt) : '暂无同步数据'}</span>
          <span>记录总数：{meta?.recordCount ?? 0}</span>
        </div>
      </section>

      <form className="search-panel" onSubmit={onSubmit}>
        <label>
          教室
          <input value={classroom} onChange={(event) => setClassroom(event.target.value)} placeholder="JA101 或 2080" />
        </label>
        <label>
          科目
          <input value={course} onChange={(event) => setCourse(event.target.value)} placeholder="大学英语" />
        </label>
        <label>
          周次
          <input value={week} onChange={(event) => setWeek(event.target.value)} placeholder="19" inputMode="numeric" />
        </label>
        <label>
          星期
          <select value={weekday} onChange={(event) => setWeekday(event.target.value)}>
            <option value="">不限</option>
            <option value="1">周一</option>
            <option value="2">周二</option>
            <option value="3">周三</option>
            <option value="4">周四</option>
            <option value="5">周五</option>
            <option value="6">周六</option>
            <option value="7">周日</option>
          </select>
        </label>
        <label>
          节次
          <input value={timeSlot} onChange={(event) => setTimeSlot(event.target.value)} placeholder="0102 / 1,2 / 1-2" />
        </label>
        <button disabled={loading} type="submit">{loading ? '查询中...' : '查询'}</button>
      </form>

      <section className="results-panel">
        <p className="message">{message}</p>
        <div className="result-list">
          {results.map((record, index) => (
            <article className="result-card" key={`${record.classroomId}-${record.weekInfo}-${record.courseName}-${index}`}>
              <h2>{record.courseName}</h2>
              <p>{record.classroomName} / {record.classroomId}</p>
              <p>第 {record.week} 周，星期 {record.weekday}，节次 {record.timeSlot}</p>
              <p>{record.startTime} - {record.endTime}</p>
              <p>{record.examStatus}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  )
}
```

- [ ] **Step 2: Add responsive styles**

Append to `app/globals.css`:

```css
.page-shell {
  width: min(1120px, calc(100% - 32px));
  margin: 0 auto;
  padding: 48px 0;
}

.hero {
  padding: 32px;
  border-radius: 28px;
  color: white;
  background: linear-gradient(135deg, #174ea6, #6a4cff);
  box-shadow: 0 20px 60px rgba(23, 78, 166, 0.24);
}

.hero h1 {
  margin: 8px 0 12px;
  font-size: clamp(32px, 6vw, 56px);
}

.eyebrow {
  margin: 0;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.8;
}

.status-card {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 24px;
}

.status-card span {
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
}

.search-panel {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
  margin: 24px 0;
  padding: 20px;
  border-radius: 24px;
  background: white;
  box-shadow: 0 12px 40px rgba(23, 32, 51, 0.08);
}

.search-panel label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-weight: 700;
}

.search-panel input,
.search-panel select {
  width: 100%;
  border: 1px solid #d9dfec;
  border-radius: 14px;
  padding: 12px;
}

.search-panel button {
  align-self: end;
  border: 0;
  border-radius: 14px;
  padding: 13px 18px;
  color: white;
  background: #174ea6;
  cursor: pointer;
}

.search-panel button:disabled {
  opacity: 0.7;
  cursor: wait;
}

.message {
  color: #5f6b85;
}

.result-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}

.result-card {
  padding: 20px;
  border-radius: 20px;
  background: white;
  box-shadow: 0 10px 30px rgba(23, 32, 51, 0.06);
}

.result-card h2 {
  margin: 0 0 12px;
  font-size: 18px;
}

@media (max-width: 900px) {
  .search-panel {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 3: Verify frontend build**

Run: `npm run typecheck`

Expected: PASS.

Run: `npm run build`

Expected: PASS.

- [ ] **Step 4: Commit page**

Run:

```bash
git add app/page.tsx app/globals.css
git commit -m "feat(page): 添加公开考试查询页面"
```

## Task 7: Add JSON Upload Support to Crawler

**Files:**
- Modify: `crawl_exams.py`

- [ ] **Step 1: Add JSON row conversion and upload helpers**

Modify `crawl_exams.py` to add these imports near the existing imports:

```python
import os
from datetime import datetime, timezone
```

Add these functions after `class ExamRecord`:

```python
def record_to_json(rec):
    return {
        "classroomName": rec.classroom_name,
        "classroomId": rec.classroom_id,
        "examStatus": rec.exam_status,
        "courseName": rec.course_name,
        "examTime": rec.exam_date,
        "weekInfo": rec.week_info,
        "weekday": rec.weekday,
        "timeSlot": rec.time_slot,
        "startTime": rec.start_time,
        "endTime": rec.end_time,
        "invigilator": rec.invigilator,
        "week": rec.week_range,
    }


def upload_payload(upload_url, upload_secret, payload):
    headers = {
        "Authorization": f"Bearer {upload_secret}",
        "Content-Type": "application/json; charset=utf-8",
    }
    resp = requests.post(upload_url, headers=headers, json=payload, timeout=60)
    if resp.status_code >= 400:
        print(f"[!] 上传失败: HTTP {resp.status_code}")
        print(resp.text)
        return False
    print(f"[+] 上传成功: HTTP {resp.status_code}")
    print(resp.text)
    return True
```

- [ ] **Step 2: Collect JSON records during crawl**

Modify `ResultWriter.__init__` to initialize `json_records`:

```python
    def __init__(self, output_path, fmt="csv"):
        self.output_path = output_path
        self.fmt = fmt
        self.lock = threading.Lock()
        self.count = 0
        self.json_records = []
        self._init_file()
```

Modify `ResultWriter.write` inside the lock before format-specific writes:

```python
            for rec in records:
                self.json_records.append(record_to_json(rec))
```

Add this method to `ResultWriter`:

```python
    def get_json_records(self):
        with self.lock:
            return list(self.json_records)
```

- [ ] **Step 3: Add JSON payload output and upload after crawl**

Add this function before `crawl(args)`:

```python
def build_payload(args, records):
    return {
        "source": "local-cron",
        "semester": args.semester,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "records": records,
    }
```

Modify the end of `crawl(args)` after `writer.finalize()`:

```python
    payload = build_payload(args, writer.get_json_records())

    if args.json_output:
        with open(args.json_output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"[+] JSON结果已保存到: {args.json_output}")

    if args.upload_url or args.upload:
        upload_url = args.upload_url or os.getenv("VERCEL_UPLOAD_URL")
        upload_secret = args.upload_secret or os.getenv("VERCEL_UPLOAD_SECRET")
        if not upload_url or not upload_secret:
            print("[!] 上传失败: 缺少 VERCEL_UPLOAD_URL 或 VERCEL_UPLOAD_SECRET")
            return 1
        if not upload_payload(upload_url, upload_secret, payload):
            return 1
```

Change the final line of `crawl(args)` to return success:

```python
    return 0
```

Replace these existing early exits in `crawl(args)` with explicit status codes:

```python
    if kbjcmsid is None:
        print("[!] Cookie无效，无法继续")
        return 1
```

```python
    if is_login_page(grid_html):
        print("[!] Cookie无效，服务器返回了登录页面")
        return 1
```

```python
    if not classrooms:
        print("[!] 未找到教室数据")
        return 1
```

```python
    if not exam_tasks:
        print("[!] 没有找到考试安排")
        return 0
```

- [ ] **Step 4: Add CLI flags and exit code propagation**

Add parser arguments in `main()`:

```python
    parser.add_argument("--json-output", default="",
                        help="输出JSON上传载荷路径 (可选)")
    parser.add_argument("--upload", action="store_true",
                        help="爬取完成后上传到Vercel接口")
    parser.add_argument("--upload-url", default="",
                        help="Vercel上传接口URL，默认读取VERCEL_UPLOAD_URL")
    parser.add_argument("--upload-secret", default="",
                        help="Vercel上传密钥，默认读取VERCEL_UPLOAD_SECRET")
```

Change the end of `main()`:

```python
    return crawl(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Verify Python syntax**

Run: `python3 -m py_compile crawl_exams.py`

Expected: command exits with status 0.

- [ ] **Step 6: Commit crawler upload support**

Run:

```bash
git add crawl_exams.py
git commit -m "feat(crawl_exams.py): 添加JSON上传同步能力"
```

## Task 8: End-to-End Verification and Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README with environment and usage**

Replace `README.md` with:

```md
# easy-qfnu-exam

qfnu 考试安排自助查询，支持本地爬虫定时同步到 Vercel Redis，并通过公开网页查询。

## Vercel 环境变量

`UPSTASH_REDIS_REST_URL`：Vercel Marketplace Upstash Redis REST URL。

`UPSTASH_REDIS_REST_TOKEN`：Vercel Marketplace Upstash Redis REST Token。

`UPLOAD_SECRET`：上传接口密钥。

## 本地爬虫上传

```bash
export VERCEL_UPLOAD_URL="https://your-domain.vercel.app/api/upload"
export VERCEL_UPLOAD_SECRET="your-secret"
python3 crawl_exams.py -c "JSESSIONID=xxx" --json-output exams.json --upload
```

## 查询

打开 Vercel 站点首页，输入教室、科目、周次、星期或节次查询。
```

- [ ] **Step 2: Run full checks**

Run: `npm test`

Expected: all Vitest tests pass.

Run: `npm run typecheck`

Expected: TypeScript exits with status 0.

Run: `npm run build`

Expected: Next.js build exits with status 0.

Run: `python3 -m py_compile crawl_exams.py`

Expected: Python compile exits with status 0.

- [ ] **Step 3: Commit docs and verified state**

Run:

```bash
git add README.md
git commit -m "docs(README.md): 补充部署和同步说明"
```

## Self-Review Notes

Spec coverage:

1. Next.js app scaffold is covered by Task 1.
2. Redis-backed KV semantics are covered by Task 4.
3. Protected upload route is covered by Task 5.
4. Public search route is covered by Task 5.
5. Query page with update time is covered by Task 6.
6. Real crawler field mapping and JSON upload are covered by Task 7.
7. Error handling is covered by route status returns and crawler upload failure behavior.
8. Verification is covered by Task 8.

Placeholder scan: no unresolved markers or unspecified implementation steps are intentionally left.

Type consistency: record fields use `classroomName`, `classroomId`, `examStatus`, `courseName`, `examTime`, `weekInfo`, `weekday`, `timeSlot`, `startTime`, `endTime`, `invigilator`, and `week` consistently across TypeScript and Python.
