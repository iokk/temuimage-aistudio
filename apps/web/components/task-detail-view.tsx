"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"

import { getJob, type JobRecord } from "../lib/job-client"

const statusMap: Record<string, string> = {
  queued: "排队中",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
}

const pageHrefMap: Record<string, string> = {
  工作台: "/",
  标题优化: "/title",
  图片翻译: "/translate",
  快速出图: "/quick",
  批量出图: "/batch",
}

function renderJsonBlock(value: Record<string, unknown>) {
  return JSON.stringify(value, null, 2)
}

function readString(value: unknown) {
  return typeof value === "string" ? value : ""
}

function readStringArray(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : []
}

function readObjectArray(value: unknown) {
  return Array.isArray(value)
    ? value.filter(
        (item): item is Record<string, unknown> => Boolean(item) && typeof item === "object",
      )
    : []
}

function getPageHref(page: string) {
  return pageHrefMap[page] || "/"
}

function StructuredResult({
  taskType,
  result,
}: {
  taskType: string
  result: Record<string, unknown>
}) {
  if (taskType === "title_generation") {
    const titles = readStringArray(result.titles)
    return (
      <div className="space-y-3">
        <p className="text-sm text-slate-500">模型：{readString(result.model) || "未返回"}</p>
        {titles.map((title, index) => (
          <div key={`${title}-${index}`} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-800">
            {index + 1}. {title}
          </div>
        ))}
      </div>
    )
  }

  if (taskType === "image_translate") {
    const sourceLines = readStringArray(result.source_lines)
    const translatedLines = readStringArray(result.translated_lines)
    const capabilityReasons = readStringArray(result.capability_reasons)
    return (
      <div className="space-y-4">
        <p className="text-sm text-slate-500">Provider：{readString(result.provider)} / {readString(result.image_model)}</p>
        <p className="text-sm text-slate-600">{readString(result.provider_message)}</p>
        {capabilityReasons.length > 0 ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {capabilityReasons.map((reason, index) => (
              <p key={`${reason}-${index}`}>{reason}</p>
            ))}
          </div>
        ) : null}
        <div className="grid gap-4 lg:grid-cols-2">
          <div>
            <p className="text-sm font-semibold text-slate-900">原文</p>
            <div className="mt-3 space-y-2">
              {sourceLines.map((line, index) => (
                <div key={`${line}-${index}`} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-700">
                  {line}
                </div>
              ))}
            </div>
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900">译文</p>
            <div className="mt-3 space-y-2">
              {translatedLines.map((line, index) => (
                <div key={`${line}-${index}`} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-700">
                  {line}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (taskType === "quick_generation") {
    const outputs = readObjectArray(result.outputs)
    const titles = readStringArray(result.titles)
    return (
      <div className="space-y-4">
        <p className="text-sm text-slate-500">图片模型：{readString(result.image_model)} · 标题模型：{readString(result.title_model)}</p>
        <p className="text-sm text-slate-600">图需摘要：{readString(result.prompt_summary)}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          {outputs.map((item, index) => (
            <div key={`${readString(item.id) || index}`} className="rounded-2xl border border-slate-200 p-4">
              <p className="text-sm font-semibold text-slate-900">{readString(item.label)}</p>
              <p className="mt-2 text-sm leading-6 text-slate-500">{readString(item.preview_text)}</p>
            </div>
          ))}
        </div>
        {titles.length > 0 ? (
          <div className="space-y-2">
            <p className="text-sm font-semibold text-slate-900">附带标题</p>
            {titles.map((title, index) => (
              <div key={`${title}-${index}`} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-700">
                {index + 1}. {title}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    )
  }

  if (taskType === "batch_generation") {
    const outputs = readObjectArray(result.outputs)
    return (
      <div className="space-y-4">
        <p className="text-sm text-slate-500">图片模型：{readString(result.image_model)} · 标题模型：{readString(result.title_model)}</p>
        <p className="text-sm text-slate-600">图需摘要：{readString(result.brief_summary)}</p>
        <p className="text-sm text-slate-500">输出数量：{String(result.total_outputs || outputs.length)}</p>
        <div className="space-y-3">
          {outputs.map((item, index) => (
            <div key={`${readString(item.id) || index}`} className="rounded-2xl border border-slate-200 p-4">
              <p className="text-sm font-semibold text-slate-900">{readString(item.label)}</p>
              <p className="mt-2 text-sm leading-6 text-slate-500">{readString(item.brief)}</p>
              {readString(item.title) ? (
                <p className="mt-3 text-sm text-slate-700">标题候选：{readString(item.title)}</p>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <pre className="overflow-x-auto rounded-2xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">
      {renderJsonBlock(result)}
    </pre>
  )
}

export function TaskDetailView({
  apiBaseUrl,
  initialJob,
}: {
  apiBaseUrl: string
  initialJob: JobRecord
}) {
  const normalizedApiBaseUrl = useMemo(() => apiBaseUrl.replace(/\/$/, ""), [apiBaseUrl])
  const [job, setJob] = useState(initialJob)

  useEffect(() => {
    if (!["queued", "running"].includes(job.status)) {
      return
    }

    const timer = window.setInterval(async () => {
      try {
        const payload = await getJob(normalizedApiBaseUrl, job.id)
        setJob(payload.job)
      } catch {
        return
      }
    }, 3000)

    return () => {
      window.clearInterval(timer)
    }
  }, [job.id, job.status, normalizedApiBaseUrl])

  return (
    <section className="grid gap-6">
      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-900">
              {job.icon} {job.summary}
            </p>
            <p className="mt-2 text-sm text-slate-500">
              任务 ID：{job.id} · 页面：{job.page}
            </p>
            <p className="mt-1 text-sm text-slate-500">
              最近更新时间：{new Date(job.updated_at).toLocaleString("zh-CN")}
            </p>
          </div>
          <div className="text-right text-sm text-slate-500">
            <p>{statusMap[job.status] || job.status}</p>
            <p className="mt-1">{new Date(job.created_at).toLocaleString("zh-CN")}</p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/tasks"
            className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50"
          >
            返回任务中心
          </Link>
          <Link
            href={getPageHref(job.page)}
            className="rounded-2xl bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-500"
          >
            返回对应页面
          </Link>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h3 className="text-xl font-bold text-slate-950">任务参数</h3>
          <pre className="mt-4 overflow-x-auto rounded-2xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">
            {renderJsonBlock(job.payload)}
          </pre>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h3 className="text-xl font-bold text-slate-950">结构化结果</h3>
          <div className="mt-4">
            <StructuredResult taskType={job.task_type} result={job.result} />
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <h3 className="text-xl font-bold text-slate-950">状态时间线</h3>
        <div className="mt-4 space-y-3">
          {job.history.map((entry, index) => (
            <div key={`${entry.at}-${index}`} className="rounded-2xl border border-slate-200 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm font-semibold text-slate-900">
                  {statusMap[entry.status] || entry.status}
                </p>
                <p className="text-sm text-slate-500">
                  {new Date(entry.at).toLocaleString("zh-CN")}
                </p>
              </div>
              <p className="mt-2 text-sm leading-7 text-slate-600">{entry.message}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <h3 className="text-xl font-bold text-slate-950">原始 JSON</h3>
        <pre className="mt-4 overflow-x-auto rounded-2xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">
          {renderJsonBlock(job.result)}
        </pre>
      </div>

      {readString(job.result.error) ? (
        <div className="rounded-3xl border border-rose-200 bg-rose-50 p-8 shadow-sm">
          <h3 className="text-xl font-bold text-rose-800">错误信息</h3>
          <p className="mt-4 text-sm leading-7 text-rose-700">
            {readString(job.result.error)}
          </p>
        </div>
      ) : null}
    </section>
  )
}
