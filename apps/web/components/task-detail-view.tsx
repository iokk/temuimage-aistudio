"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"

import {
  buildJobArtifactsZipUrl,
  buildTranslateOutputsZipUrl,
  getJob,
  type JobRecord,
} from "../lib/job-client"
import { TitleReviewResults } from "./title-review-results"

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

type TranslateBatchOutput = {
  id: string
  label: string
  raw_name: string
  status: string
  artifact_data_url: string
  source_lines: string[]
  translated_lines: string[]
  filename: string
  error: string
}

type GenericArtifactOutput = {
  id: string
  type: string
  label: string
  status: string
  artifact_data_url: string
  prompt: string
  error: string
  title: string
  filename: string
}

type BatchAnchor = {
  product_name_en: string
  product_name_zh: string
  primary_category: string
  visual_attrs: string[]
  confidence: number
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

function readNumber(value: unknown) {
  if (typeof value === "number") {
    return value
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}

function fallbackTranslateDownloadName(item: TranslateBatchOutput) {
  const filename = item.filename.trim()
  if (filename) {
    return filename.toLowerCase().endsWith(".png") ? filename : `${filename}.png`
  }

  const rawName = item.raw_name.trim().replace(/\.[^/.]+$/, "")
  if (rawName) {
    return `${rawName}-translated.png`
  }

  const label = item.label.trim().replace(/\s+/g, "-")
  return `${label || item.id || "translated-image"}.png`
}

function fallbackArtifactDownloadName(item: GenericArtifactOutput) {
  const filename = item.filename.trim()
  if (filename) {
    return filename.toLowerCase().endsWith(".png") ? filename : `${filename}.png`
  }

  const label = item.label.trim().replace(/\s+/g, "-")
  return `${label || item.id || "artifact-output"}.png`
}

function readTranslateBatchOutput(item: Record<string, unknown>): TranslateBatchOutput {
  return {
    id: readString(item.id),
    label: readString(item.label) || "译后图片",
    raw_name: readString(item.raw_name),
    status: readString(item.status),
    artifact_data_url: readString(item.artifact_data_url),
    source_lines: readStringArray(item.source_lines),
    translated_lines: readStringArray(item.translated_lines),
    filename: readString(item.filename),
    error: readString(item.error),
  }
}

function readGenericArtifactOutput(item: Record<string, unknown>): GenericArtifactOutput {
  return {
    id: readString(item.id),
    type: readString(item.type),
    label: readString(item.label) || "输出结果",
    status: readString(item.status),
    artifact_data_url: readString(item.artifact_data_url),
    prompt: readString(item.prompt),
    error: readString(item.error),
    title: readString(item.title),
    filename: readString(item.filename),
  }
}

function readBatchAnchor(value: unknown) {
  if (!value || typeof value !== "object") {
    return null
  }

  const anchor = value as Record<string, unknown>
  return {
    product_name_en: readString(anchor.product_name_en),
    product_name_zh: readString(anchor.product_name_zh),
    primary_category: readString(anchor.primary_category),
    visual_attrs: readStringArray(anchor.visual_attrs),
    confidence: readNumber(anchor.confidence),
  } satisfies BatchAnchor
}

function readRecord(value: unknown) {
  if (!value || typeof value !== "object") {
    return null
  }
  return value as Record<string, unknown>
}

function formatAnchorConfidence(value: number) {
  if (!Number.isFinite(value) || value <= 0) {
    return "未返回"
  }
  if (value <= 1) {
    return `${Math.round(value * 100)}%`
  }
  return `${Math.round(value)}%`
}

function OutputCard({ item }: { item: Record<string, unknown> }) {
  const output = readGenericArtifactOutput(item)

  return (
    <div className="rounded-2xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">{output.label}</p>
          {output.filename ? <p className="mt-1 text-xs text-slate-500">{output.filename}</p> : null}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {output.status ? <p className="text-xs font-medium text-slate-500">{statusMap[output.status] || output.status}</p> : null}
          {output.artifact_data_url ? (
            <a
              href={output.artifact_data_url}
              download={fallbackArtifactDownloadName(output)}
              className="rounded-2xl border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50"
            >
              下载 PNG
            </a>
          ) : null}
        </div>
      </div>
      {output.artifact_data_url ? (
        <img
          src={output.artifact_data_url}
          alt={output.label}
          className="mt-3 w-full rounded-2xl border border-slate-200 object-cover"
        />
      ) : null}
      {output.prompt ? <p className="mt-3 text-sm leading-6 text-slate-500">{output.prompt}</p> : null}
      {output.title ? <p className="mt-3 text-sm text-slate-700">标题候选：{output.title}</p> : null}
      {output.error ? <p className="mt-3 text-sm leading-6 text-rose-600">{output.error}</p> : null}
    </div>
  )
}

function BatchAnchorCard({ anchor }: { anchor: BatchAnchor | null }) {
  if (!anchor) {
    return null
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
      <p className="font-semibold text-slate-900">批次锚点摘要</p>
      <div className="mt-3 space-y-2">
        <p>英文品名：{anchor.product_name_en || "未返回"}</p>
        <p>中文品名：{anchor.product_name_zh || "未返回"}</p>
        <p>主类目：{anchor.primary_category || "未返回"}</p>
        <p>置信度：{formatAnchorConfidence(anchor.confidence)}</p>
        <div>
          <p className="text-slate-900">视觉属性</p>
          {anchor.visual_attrs.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-2">
              {anchor.visual_attrs.map((item, index) => (
                <span key={`${item}-${index}`} className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
                  {item}
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate-500">未返回视觉属性。</p>
          )}
        </div>
      </div>
    </div>
  )
}

function TranslateImageBatchResult({
  apiBaseUrl,
  jobId,
  result,
}: {
  apiBaseUrl: string
  jobId: string
  result: Record<string, unknown>
}) {
  const outputs = readObjectArray(result.outputs).map(readTranslateBatchOutput)
  const [selectedOutputId, setSelectedOutputId] = useState("")
  const selectedOutput = outputs.find((item) => item.id === selectedOutputId) || outputs[0] || null
  const failedCount = readNumber(result.failed_outputs) || outputs.filter((item) => item.status === "failed").length
  const completedCount = readNumber(result.completed_outputs) || outputs.filter((item) => item.status === "completed").length
  const totalCount = readNumber(result.total_outputs) || outputs.length
  const errors = readStringArray(result.errors)
  const zipExportUrl = buildTranslateOutputsZipUrl(apiBaseUrl, jobId)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-2 text-sm text-slate-500">
          <p>Provider：{readString(result.provider) || "未返回"} / {readString(result.image_model) || "未返回"}</p>
          <p>分析模型：{readString(result.analysis_model) || "未返回"}</p>
          <p>执行模式：{readString(result.execution_mode) || "image_batch"}</p>
        </div>
        <div className="flex flex-wrap gap-3">
          {selectedOutput?.artifact_data_url ? (
            <a
              href={selectedOutput.artifact_data_url}
              download={fallbackTranslateDownloadName(selectedOutput)}
              className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50"
            >
              下载当前 PNG
            </a>
          ) : null}
          <a
            href={zipExportUrl}
            className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50"
          >
            导出 ZIP
          </a>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        <p>总计：{totalCount} 张</p>
        <p>成功：{completedCount} 张</p>
        <p>失败：{failedCount} 张</p>
      </div>

      {readString(result.provider_message) ? (
        <p className="text-sm leading-6 text-slate-600">{readString(result.provider_message)}</p>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {outputs.map((item) => {
          const isActive = item.id === selectedOutput?.id
          return (
            <button
              key={item.id || item.label}
              type="button"
              onClick={() => setSelectedOutputId(item.id)}
              className={`rounded-2xl border p-3 text-left transition ${
                isActive
                  ? "border-sky-400 bg-sky-50"
                  : "border-slate-200 bg-white hover:border-sky-300"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-slate-900">{item.label}</p>
                <p className={`text-xs font-medium ${item.status === "failed" ? "text-rose-600" : "text-slate-500"}`}>
                  {item.status === "completed" ? "已完成" : item.status === "failed" ? "失败" : item.status || "处理中"}
                </p>
              </div>
              <p className="mt-1 truncate text-xs text-slate-500">{item.raw_name || fallbackTranslateDownloadName(item)}</p>
            </button>
          )
        })}
      </div>

      {selectedOutput ? (
        <div className="rounded-2xl border border-slate-200 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-900">{selectedOutput.label}</p>
              <p className="mt-1 text-xs text-slate-500">源文件：{selectedOutput.raw_name || "未返回"}</p>
            </div>
            <p className={`text-xs font-medium ${selectedOutput.status === "failed" ? "text-rose-600" : "text-slate-500"}`}>
              {selectedOutput.status === "completed" ? "已完成" : selectedOutput.status === "failed" ? "失败" : selectedOutput.status || "处理中"}
            </p>
          </div>

          {selectedOutput.artifact_data_url ? (
            <img
              src={selectedOutput.artifact_data_url}
              alt={selectedOutput.label}
              className="mt-4 w-full rounded-2xl border border-slate-200 object-cover"
            />
          ) : (
            <div className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-sm text-slate-500">
              当前条目未生成译后图片。
            </div>
          )}

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div>
              <p className="text-sm font-semibold text-slate-900">原文</p>
              <div className="mt-3 space-y-2">
                {selectedOutput.source_lines.length > 0 ? (
                  selectedOutput.source_lines.map((line, index) => (
                    <div key={`${line}-${index}`} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-700">
                      {line}
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
                    未返回原文分行。
                  </div>
                )}
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">译文</p>
              <div className="mt-3 space-y-2">
                {selectedOutput.translated_lines.length > 0 ? (
                  selectedOutput.translated_lines.map((line, index) => (
                    <div key={`${line}-${index}`} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-700">
                      {line}
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
                    未返回译文分行。
                  </div>
                )}
              </div>
            </div>
          </div>

          {selectedOutput.error ? (
            <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {selectedOutput.error}
            </div>
          ) : null}
        </div>
      ) : null}

      {errors.length > 0 ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {errors.map((entry, index) => (
            <p key={`${entry}-${index}`}>{entry}</p>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function getPageHref(page: string) {
  return pageHrefMap[page] || "/"
}

function StructuredResult({
  taskType,
  result,
  apiBaseUrl,
  jobId,
}: {
  taskType: string
  result: Record<string, unknown>
  apiBaseUrl: string
  jobId: string
}) {
  if (taskType === "title_generation") {
    const executionContext = readRecord(result.execution_context)
    const executionMode = readString(result.execution_mode)
    const uploadCount = readNumber(result.upload_count)
    const referenceCount = readNumber(result.reference_count)
    return (
      <div className="space-y-3">
        <p className="text-sm text-slate-500">Provider：{readString(result.provider) || "未返回"} · 模型：{readString(result.model) || "未返回"}</p>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          <p>执行来源：{readString(result.source) || "未返回"}</p>
          {executionMode ? <p>执行模式：{executionMode}</p> : null}
          {(readString(result.template_name) || readString(result.template_key)) ? (
            <p>
              标题模板：{readString(result.template_name) || "未命名模板"}
              {readString(result.template_key) ? ` · ${readString(result.template_key)}` : ""}
            </p>
          ) : null}
          {readString(result.compliance_mode) ? <p>合规模式：{readString(result.compliance_mode)}</p> : null}
          {("upload_count" in result) ? <p>已上传商品图：{uploadCount}</p> : null}
          {("reference_count" in result) ? <p>参与参考：{referenceCount}</p> : null}
          <p>Tokens：{readNumber(result.tokens_used)}</p>
          {executionContext ? (
            <>
              <p>配置来源：{readString(executionContext.config_source) || "未返回"}</p>
              <p>项目：{readString(executionContext.project_name) || "未返回"}{readString(executionContext.project_slug) ? ` · ${readString(executionContext.project_slug)}` : ""}</p>
            </>
          ) : null}
        </div>
        <TitleReviewResults
          titlePairsSource={result.title_pairs}
          fallbackTitlesSource={result.titles}
          warningsSource={result.warnings}
          emptyMessage="该标题任务尚未返回候选结果。"
          fallbackHeading="英文标题候选"
        />
      </div>
    )
  }

  if (taskType === "image_translate") {
    const sourceLines = readStringArray(result.source_lines)
    const translatedLines = readStringArray(result.translated_lines)
    const capabilityReasons = readStringArray(result.capability_reasons)
    const executionMode = readString(result.execution_mode) || "text"
    const outputs = readObjectArray(result.outputs)

    if (executionMode === "image_batch" && outputs.length > 0) {
      return <TranslateImageBatchResult apiBaseUrl={apiBaseUrl} jobId={jobId} result={result} />
    }

    return (
      <div className="space-y-4">
        <p className="text-sm text-slate-500">Provider：{readString(result.provider) || "未返回"} / {readString(result.image_model) || "未返回"}</p>
        <p className="text-sm text-slate-600">{readString(result.provider_message)}</p>
        <p className="text-sm text-slate-500">执行模式：{executionMode}</p>
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
    const titleWarnings = readStringArray(result.title_warnings)
    const errors = readStringArray(result.errors)
    const executionMode = readString(result.execution_mode) || "text"
    const uploadCount = readNumber(result.upload_count)
    const referenceCount = readNumber(result.reference_count)
    const hasArtifacts = outputs.some((item) => readString(item.artifact_data_url))
    const zipExportUrl = hasArtifacts ? buildJobArtifactsZipUrl(apiBaseUrl, jobId) : ""

    return (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <p className="text-sm text-slate-500">Provider：{readString(result.provider)} · 图片模型：{readString(result.image_model)} · 标题模型：{readString(result.title_model)}</p>
            <p className="text-sm text-slate-600">图需摘要：{readString(result.prompt_summary)}</p>
          </div>
          {zipExportUrl ? (
            <a
              href={zipExportUrl}
              className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50"
            >
              导出 ZIP
            </a>
          ) : null}
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          <p>执行模式：{executionMode}</p>
          <p>已上传商品图：{uploadCount}</p>
          <p>参与参考：{referenceCount}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {outputs.map((item, index) => <OutputCard key={`${readString(item.id) || index}`} item={item} />)}
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
        {titleWarnings.length > 0 ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
            {titleWarnings.map((warning, index) => (
              <p key={`${warning}-${index}`}>{warning}</p>
            ))}
          </div>
        ) : null}
        {errors.length > 0 ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {errors.map((entry, index) => (
              <p key={`${entry}-${index}`}>{entry}</p>
            ))}
          </div>
        ) : null}
      </div>
    )
  }

  if (taskType === "batch_generation") {
    const outputs = readObjectArray(result.outputs)
    const titles = readStringArray(result.titles)
    const titleWarnings = readStringArray(result.title_warnings)
    const errors = readStringArray(result.errors)
    const executionMode = readString(result.execution_mode) || "text"
    const uploadCount = readNumber(result.upload_count)
    const referenceCount = readNumber(result.reference_count)
    const hasArtifacts = outputs.some((item) => readString(item.artifact_data_url))
    const zipExportUrl = hasArtifacts ? buildJobArtifactsZipUrl(apiBaseUrl, jobId) : ""
    const anchor = readBatchAnchor(result.anchor)

    return (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <p className="text-sm text-slate-500">Provider：{readString(result.provider)} · 图片模型：{readString(result.image_model)} · 标题模型：{readString(result.title_model)}</p>
            <p className="text-sm text-slate-600">图需摘要：{readString(result.brief_summary)}</p>
          </div>
          {zipExportUrl ? (
            <a
              href={zipExportUrl}
              className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50"
            >
              导出 ZIP
            </a>
          ) : null}
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            <p>执行模式：{executionMode}</p>
            <p>已上传商品图：{uploadCount}</p>
            <p>参与参考：{referenceCount}</p>
            <p>输出数量：{String(result.total_outputs || outputs.length)}</p>
            {readString(result.analysis_model) ? <p>分析模型：{readString(result.analysis_model)}</p> : null}
          </div>
          <BatchAnchorCard anchor={anchor} />
        </div>
        <div className="space-y-3">
          {outputs.map((item, index) => <OutputCard key={`${readString(item.id) || index}`} item={item} />)}
        </div>
        {titles.length > 0 ? (
          <div className="space-y-2">
            <p className="text-sm font-semibold text-slate-900">批次标题候选</p>
            {titles.map((title, index) => (
              <div key={`${title}-${index}`} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-700">
                {index + 1}. {title}
              </div>
            ))}
          </div>
        ) : null}
        {titleWarnings.length > 0 ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
            {titleWarnings.map((warning, index) => (
              <p key={`${warning}-${index}`}>{warning}</p>
            ))}
          </div>
        ) : null}
        {errors.length > 0 ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {errors.map((entry, index) => (
              <p key={`${entry}-${index}`}>{entry}</p>
            ))}
          </div>
        ) : null}
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
  const taskCenterReturnLabel = job.project
    ? `返回 ${job.project.project_name} 任务中心`
    : "返回任务中心"
  const pageReturnLabel = job.project
    ? `返回该项目的${job.page}`
    : "返回对应页面"

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
            {job.project ? (
              <p className="mt-1 text-sm text-slate-500">
                所属项目：{job.project.project_name} · {job.project.project_slug}
              </p>
            ) : null}
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
            {taskCenterReturnLabel}
          </Link>
          <Link
            href={getPageHref(job.page)}
            className="rounded-2xl bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-500"
          >
            {pageReturnLabel}
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
            <StructuredResult
              taskType={job.task_type}
              result={job.result}
              apiBaseUrl={normalizedApiBaseUrl}
              jobId={job.id}
            />
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
