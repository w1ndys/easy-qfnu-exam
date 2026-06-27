'use client'

import { FormEvent, useEffect, useRef, useState } from 'react'
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
  const latestRequestId = useRef(0)

  useEffect(() => {
    let cancelled = false

    async function loadMeta() {
      try {
        const response = await fetch('/api/exams/search?limit=1')
        if (!response.ok) return

        const data = (await response.json()) as SearchResponse
        if (cancelled) return

        setMeta(data.meta)

        if (latestRequestId.current === 0) {
          setMessage(data.meta ? '请输入条件后查询' : '暂无同步数据')
        }
      } catch {
        // Initial metadata is optional; submitted searches surface their own errors.
      }
    }

    loadMeta()

    return () => {
      cancelled = true
    }
  }, [])

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const requestId = latestRequestId.current + 1
    latestRequestId.current = requestId

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
        if (response.status === 400) {
          let error = '请检查查询条件'
          try {
            const data = (await response.json()) as { error?: unknown }
            if (typeof data.error === 'string' && data.error.trim()) {
              error = data.error
            }
          } catch {
            // Fall back to a generic validation message when the API response is not JSON.
          }

          if (latestRequestId.current === requestId) {
            setMessage(`查询条件有误：${error}`)
            setResults([])
          }
          return
        }

        throw new Error(await response.text())
      }

      const data = (await response.json()) as SearchResponse
      if (latestRequestId.current !== requestId) return

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
      if (latestRequestId.current !== requestId) return

      setMessage('查询失败，请稍后再试')
      setResults([])
    } finally {
      if (latestRequestId.current === requestId) {
        setLoading(false)
      }
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
        <p className="message" role="status" aria-live="polite">{message}</p>
        <div className="result-list">
          {results.map((record, index) => (
            <article className="result-card" key={`${record.classroomId}-${record.weekInfo}-${record.courseName}-${index}`}>
              <h2>{record.courseName}</h2>
              <p>{record.classroomName} / {record.classroomId}</p>
              <p>第 {record.week} 周，星期 {record.weekday}，节次 {record.timeSlot}</p>
              <p>{record.startTime} - {record.endTime}</p>
              <p>{record.examStatus}</p>
              {record.invigilator.trim() ? <p>监考人：{record.invigilator}</p> : null}
            </article>
          ))}
        </div>
      </section>

      <section className="notice-section">
        <p className="notice-tech">
          📱 微信公众号「<strong>曲奇味卷卷</strong>」提供技术支持
        </p>
        <p className="notice-disclaimer">
          ⚠️ 我不敢保证是准的，但一定保证是从教务系统某个地方查到的，数据仅供参考，后续可能会有变化。
        </p>
        <p className="notice-tip">
          💡 本网站可以查到但教务系统里没有的原因是：<strong>已排考，未开放</strong>
        </p>
      </section>
    </main>
  )
}
