# Vercel Exam Query Design

## Goal

Build a Vercel-hosted exam query site for QFNU classroom exam data. A local server logs in to the QFNU academic system, runs the crawler on a schedule, and uploads the complete exam dataset to Vercel. The public website lets users query exam records by classroom, week, weekday, class period, and course.

## Context

The project currently contains a Python crawler, `crawl_exams.py`, copied from the local Downloads directory. A completed crawl output was inspected at `/Users/w1ndys/Downloads/exams.csv`. The CSV is GBK encoded and contains 1697 data rows plus a header.

The real CSV columns are:

```text
教室名称,教室编号,考试状态,课程名称,考试时间,周次-星期节次,星期,节次,开始时间,结束时间,监考人,周次
```

Example row:

```csv
JA101,2080,考试,大学英语2（普通）,2026-07-06 08:00~2026-07-06 10:00,"19-101,102",1,0102,8:00,9:50,,19
```

The referenced GitHub issue documents the QFNU Strongsoft academic system login flow, including captcha, `scode` / `sxh` credential encoding, session cookies, and login verification. For this project, login and crawling stay on the local server. Vercel does not handle academic-system credentials, captcha solving, or long-running crawl work.

## Recommended Architecture

Use a Next.js app on Vercel with Vercel KV storage.

The system has three parts:

1. Local cron job runs the crawler, produces JSON, and uploads it.
2. Next.js route handler `POST /api/upload` validates an upload secret and writes the dataset to Vercel KV.
3. Next.js frontend and `GET /api/exams/search` expose public search over the current dataset.

Data flow:

```text
local cron
  -> login to academic system
  -> crawl classroom exam status
  -> generate exams JSON payload
  -> POST /api/upload with upload secret
  -> Vercel KV stores new dataset version
  -> current dataset pointer switches after successful write
  -> public frontend queries current dataset
```

This keeps Vercel simple and stateless except for KV data. It also avoids placing academic-system credentials or OCR configuration in Vercel.

## Alternatives Considered

### Full JSON Dataset in Vercel KV

Store the complete current dataset and filter it in the API route. This is the recommended approach because the dataset is only about 1,000 to 2,000 records. It is simple, consistent, and easy to debug.

### KV Query Indexes

Store the dataset plus indexes by classroom, course, week, weekday, and period. This could improve query speed, but it makes uploads and future schema changes more complex. It is unnecessary for the current dataset size.

### External Database

Use Postgres, Supabase, or Neon. This is stronger for long-term history, complex SQL queries, and analytics, but it adds operational complexity that the current requirements do not need.

## Data Model

Uploaded records should map directly from the real crawl output to avoid lossy parsing.

```json
{
  "classroomName": "JA101",
  "classroomId": "2080",
  "examStatus": "考试",
  "courseName": "大学英语2（普通）",
  "examTime": "2026-07-06 08:00~2026-07-06 10:00",
  "weekInfo": "19-101,102",
  "weekday": "1",
  "timeSlot": "0102",
  "startTime": "8:00",
  "endTime": "9:50",
  "invigilator": "",
  "week": "19"
}
```

The upload payload shape is:

```json
{
  "source": "local-cron",
  "semester": "2025-2026-2",
  "generatedAt": "2026-06-26T10:00:00+08:00",
  "records": []
}
```

`generatedAt` is when the local crawler generated the payload. Vercel adds `uploadedAt` when the upload succeeds.

## KV Storage

Use a versioned write pattern.

`exam:current` stores the current public dataset:

```json
{
  "version": "20260626100000",
  "semester": "2025-2026-2",
  "generatedAt": "2026-06-26T10:00:00+08:00",
  "uploadedAt": "2026-06-26T10:01:10+08:00",
  "recordCount": 1234,
  "records": []
}
```

The upload flow writes `exam:version:<version>` first, then switches `exam:current` after validation succeeds. This prevents partially processed uploads from becoming visible.

## Upload API

Endpoint:

```text
POST /api/upload
```

Authentication:

```text
Authorization: Bearer <UPLOAD_SECRET>
```

Validation rules:

1. Reject missing or incorrect upload secret with `401`.
2. Reject malformed JSON with `400`.
3. Reject empty `records` with `400`.
4. Validate required record fields before writing KV.
5. Return `413` if the body is too large for the configured serverless limit.
6. Return `500` with a safe error message if KV write fails.

Successful response:

```json
{
  "ok": true,
  "version": "20260626100000",
  "recordCount": 1234,
  "uploadedAt": "2026-06-26T10:01:10+08:00"
}
```

The upload secret is stored only in Vercel environment variables and the local server environment. It must not be committed.

## Search API

Endpoint:

```text
GET /api/exams/search
```

Query parameters:

```text
classroom  optional classroom name or classroom ID substring
course     optional course name substring
week       optional week number, for example 19
weekday    optional weekday number, 1 through 7
timeSlot   optional period expression, for example 0102, 1,2, or 1-2
limit      optional max results, default 100
```

Response shape:

```json
{
  "meta": {
    "semester": "2025-2026-2",
    "generatedAt": "2026-06-26T10:00:00+08:00",
    "uploadedAt": "2026-06-26T10:01:10+08:00",
    "recordCount": 1234
  },
  "results": []
}
```

Filtering behavior:

1. Empty filters are ignored.
2. `classroom` matches `classroomName` and `classroomId` by substring.
3. `course` matches `courseName` by substring.
4. `week` equals `week`.
5. `weekday` equals `weekday`.
6. `timeSlot` is normalized before matching, so `0102`, `1,2`, and `1-2` can match the same record.

If there is no uploaded dataset, return `200` with empty `results` and empty or null metadata. The frontend should show `暂无同步数据`.

## Frontend

The frontend is publicly accessible and does not require login.

The page has three sections:

1. Header and data status: project title, semester, data update time, and record count.
2. Search form: classroom, course, week, weekday, and time slot.
3. Result list: course, classroom, week, weekday, period, start and end time, exam status, and optional invigilator.

The data update time must be visible on the query page. Prefer showing `uploadedAt` as `数据更新时间`. If useful, show `generatedAt` as `数据生成时间` in smaller text.

Initial page load should not show all records by default. Users search first, then see matching results. This avoids rendering about 1,000 records immediately.

Mobile layout should use a vertical form and card-style results. Desktop can use a compact form above a table or card list.

## Local Crawler Adjustments

The current crawler can keep CSV output for local inspection, but online synchronization should use JSON.

Required script changes for implementation:

1. Add JSON payload output that uses UTF-8.
2. Add optional upload mode that posts the JSON payload to `/api/upload`.
3. Read the Vercel upload URL and secret from environment variables or CLI arguments.
4. Print HTTP status code and response body when upload fails.
5. Exit with a non-zero status on crawl or upload failure so cron can detect failure.
6. Keep CSV output optional for manual debugging, but do not use CSV as the Vercel upload format.

CSV encoding should be handled carefully. The inspected completed output is GBK, while JSON should always be UTF-8.

## Error Handling

Upload API errors:

1. `401`: missing or invalid upload secret.
2. `400`: invalid JSON, empty records, or invalid field format.
3. `413`: upload payload too large.
4. `500`: KV write failed or unexpected server error.

Search API errors:

1. `400`: invalid query parameter, such as a non-numeric week.
2. `200`: no data uploaded yet, with empty results.
3. `500`: unexpected query failure.

Frontend errors:

1. Show `暂无同步数据` when no dataset exists.
2. Show `没有找到匹配的考试记录` when a query returns no matches.
3. Show `查询失败，请稍后再试` for request failures.

Local upload errors:

1. Print the upload URL host, HTTP status code, and response body.
2. Do not print the upload secret.
3. Exit non-zero on upload failure.

## Testing Strategy

Automated checks should cover:

1. Upload endpoint rejects requests without a valid secret.
2. Upload endpoint accepts a valid payload and writes the current dataset.
3. Search endpoint filters by classroom.
4. Search endpoint filters by course.
5. Search endpoint filters by week, weekday, and normalized time slot.
6. Search endpoint returns update metadata.
7. Frontend renders the data update time.

Manual end-to-end verification:

1. Generate a small sample JSON payload from local crawler data.
2. Upload it to the deployed Vercel endpoint.
3. Open the public page and confirm update time, record count, and query results.
4. Run the local upload with an invalid secret and confirm the error is explicit and the process exits non-zero.

## Implementation Scope

First implementation should include:

1. Next.js app scaffold suitable for Vercel.
2. Vercel KV integration.
3. Protected upload route.
4. Public search route.
5. Public query page with visible data update time.
6. Crawler JSON upload support.

Do not implement academic-system login inside Vercel in the first version.
