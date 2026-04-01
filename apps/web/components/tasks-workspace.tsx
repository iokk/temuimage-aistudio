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

type ProjectState = {
  project_id: string
  project_name: string
  project_slug: string
  project_status: string
} | null

const statusMap: Record<string, string> = {
  queued: "排队中",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
}

export function TasksWorkspace({
  apiBaseUrl,
  currentProject,
}: {
  apiBaseUrl: string
  currentProject: ProjectState
}) {
  const normalizedApiBaseUrl = useMemo(
    () => apiBaseUrl.replace(/\/$/, ""),
    [apiBaseUrl],
  )
  const [result, setResult] = useState<JobsResponse | null>(null)
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const [scope, setScope] = useState<"current" | "all">(
    currentProject ? "current" : "all",
  )
  const isCurrentScope = scope === "current" && Boolean(currentProject)
  const taskCenterTitle = isCurrentScope && currentProject
    ? `${currentProject.project_name} 任务中心`
    : "统一任务中心"

  useEffect(() => {
    async function loadJobs() {
      setIsLoading(true)
      setError("")

      try {
        const baseJobsListUrl = normalizedApiBaseUrl.endsWith("/api/platform")
          ? `${normalizedApiBaseUrl}/jobs/list`
          : `${normalizedApiBaseUrl}/v1/jobs/list`
        const jobsListUrl =
          scope === "current" && currentProject?.project_id
            ? `${baseJobsListUrl}?project_id=${encodeURIComponent(currentProject.project_id)}`
            : baseJobsListUrl
        const response = await fetch(jobsListUrl, {
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
  }, [currentProject?.project_id, normalizedApiBaseUrl, scope])

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
          <p className="mt-2 text-lg font-bold text-slate-950">标题、翻译、快速出图、批量出图已接入真实任务链</p>
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
              : "当前任务中心仍在内存模式，任务状态只在当前进程内保留。"}
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
              : "当前任务执行仍使用 inline 后端，适合本地单机执行。"}
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
          <div>
            <h3 className="text-2xl font-bold text-slate-950">{taskCenterTitle}</h3>
            {isCurrentScope && currentProject ? (
              <p className="mt-2 text-sm text-slate-500">
                当前仅显示该项目任务：{currentProject.project_name} · {currentProject.project_slug}
              </p>
            ) : currentProject ? (
              <p className="mt-2 text-sm text-slate-500">
                当前项目：{currentProject.project_name} · {currentProject.project_slug}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-3">
            {currentProject ? (
              <div className="flex overflow-hidden rounded-2xl border border-slate-200 text-sm">
                <button
                  type="button"
                  onClick={() => setScope("current")}
                  className={`px-4 py-2 transition ${
                    scope === "current"
                      ? "bg-sky-600 text-white"
                      : "bg-white text-slate-700 hover:bg-sky-50"
                  }`}
                >
                  当前项目
                </button>
                <button
                  type="button"
                  onClick={() => setScope("all")}
                  className={`border-l border-slate-200 px-4 py-2 transition ${
                    scope === "all"
                      ? "bg-sky-600 text-white"
                      : "bg-white text-slate-700 hover:bg-sky-50"
                  }`}
                >
                  全部任务
                </button>
              </div>
            ) : null}
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50"
            >
              刷新
            </button>
          </div>
        </div>

        {isLoading ? <p className="mt-4 text-sm text-slate-500">{isCurrentScope ? "正在加载当前项目任务..." : "正在加载任务..."}</p> : null}
        {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}

        {!isLoading && !error && result?.items.length === 0 ? (
          <p className="mt-4 text-sm leading-7 text-slate-500">
            {isCurrentScope
              ? "当前项目下还没有任务。现在从 `标题优化`、`图片翻译`、`快速出图` 或 `批量出图` 页面提交一次真实任务，就会自动出现在这里。"
              : "还没有任务。现在从 `标题优化`、`图片翻译`、`快速出图` 或 `批量出图` 页面提交一次真实任务，就会自动出现在这里。"}
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
                  {item.project ? (
                    <p className="mt-2 inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                      {item.project.project_name} · {item.project.project_slug}
                    </p>
                  ) : null}
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
