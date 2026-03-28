"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"

import type { JobRecord } from "../lib/job-client"

type JobsResponse = {
  items: JobRecord[]
  pending_count: number
  total: number
  active_backend: string
  preferred_backend: string
  fallback_reason: string
  persistence_ready: boolean
  active_execution_backend: string
  preferred_execution_backend: string
  execution_fallback_reason: string
  execution_queue_ready: boolean
  execution_storage_compatible: boolean
}

const statusMap: Record<string, string> = {
  queued: "排队中",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
}

export function TasksWorkspace({ apiBaseUrl }: { apiBaseUrl: string }) {
  const normalizedApiBaseUrl = useMemo(
    () => apiBaseUrl.replace(/\/$/, ""),
    [apiBaseUrl],
  )
  const [result, setResult] = useState<JobsResponse | null>(null)
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    async function loadJobs() {
      setIsLoading(true)
      setError("")

      try {
        const response = await fetch(`${normalizedApiBaseUrl}/v1/jobs/list`, {
          cache: "no-store",
        })
        if (!response.ok) {
          throw new Error("任务中心暂时不可用，请稍后刷新。")
        }
        const payload = (await response.json()) as JobsResponse
        setResult(payload)
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "任务中心暂时不可用，请稍后刷新。",
        )
      } finally {
        setIsLoading(false)
      }
    }

    void loadJobs()

    const timer = window.setInterval(() => {
      void loadJobs()
    }, 5000)

    return () => {
      window.clearInterval(timer)
    }
  }, [normalizedApiBaseUrl])

  return (
    <section className="grid gap-6">
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-500">任务总数</p>
          <p className="mt-2 text-3xl font-black text-slate-950">{result?.total ?? 0}</p>
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-500">进行中</p>
          <p className="mt-2 text-3xl font-black text-slate-950">{result?.pending_count ?? 0}</p>
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-500">当前阶段</p>
          <p className="mt-2 text-lg font-bold text-slate-950">标题优化 + 图片翻译已接入</p>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm text-slate-500">任务存储后端</p>
            <p className="mt-2 text-lg font-bold text-slate-950">
              {result?.active_backend || "memory"}
            </p>
          </div>
          <div className="text-sm text-slate-500">
            期望后端：{result?.preferred_backend || "memory"}
          </div>
        </div>
        {result?.fallback_reason ? (
          <p className="mt-3 text-sm text-amber-700">
            当前已回退到内存模式：{result.fallback_reason}
          </p>
        ) : (
          <p className="mt-3 text-sm text-slate-500">
            {result?.persistence_ready
              ? "当前任务中心已进入数据库持久化模式。"
              : "当前任务中心仍在内存模式，适合原型阶段。"}
          </p>
        )}
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm text-slate-500">异步执行后端</p>
            <p className="mt-2 text-lg font-bold text-slate-950">
              {result?.active_execution_backend || "inline"}
            </p>
          </div>
          <div className="text-sm text-slate-500">
            期望执行：{result?.preferred_execution_backend || "inline"}
          </div>
        </div>
        {result?.execution_fallback_reason ? (
          <p className="mt-3 text-sm text-amber-700">
            当前已回退到 inline：{result.execution_fallback_reason}
          </p>
        ) : (
          <p className="mt-3 text-sm text-slate-500">
            {result?.execution_queue_ready
              ? "当前任务执行已进入队列后端。"
              : "当前任务执行仍使用 inline 后端，适合本地原型阶段。"}
          </p>
        )}
        {!result?.execution_storage_compatible ? (
          <p className="mt-2 text-sm text-rose-700">
            当前 `celery` 与非持久化任务存储不兼容，系统会自动保持在 `inline`。
          </p>
        ) : null}
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-2xl font-bold text-slate-950">统一任务中心</h3>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50"
          >
            刷新
          </button>
        </div>

        {isLoading ? <p className="mt-4 text-sm text-slate-500">正在加载任务...</p> : null}
        {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}

        {!isLoading && !error && result?.items.length === 0 ? (
          <p className="mt-4 text-sm leading-7 text-slate-500">
            还没有任务。现在从 `标题优化` 或 `图片翻译` 页面生成一次预览，就会自动出现在这里。
          </p>
        ) : null}

        <div className="mt-6 space-y-3">
          {result?.items.map((item) => (
            <Link
              key={item.id}
              href={`/tasks/${item.id}`}
              className="rounded-2xl border border-slate-200 px-5 py-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    {item.icon} {item.title}
                  </p>
                  <p className="mt-1 text-sm text-slate-500">{item.summary}</p>
                </div>
                <div className="text-right text-sm text-slate-500">
                  <p>{statusMap[item.status] || item.status}</p>
                  <p className="mt-1">{new Date(item.created_at).toLocaleString("zh-CN")}</p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  )
}
