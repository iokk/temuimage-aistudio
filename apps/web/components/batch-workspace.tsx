"use client"

import Link from "next/link"
import {
  useMemo,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react"

import {
  buildJobArtifactsZipUrl,
  submitAsyncJob,
  type ImageUploadItem,
  waitForJobCompletion,
} from "../lib/job-client"
import type { RuntimePayload } from "../lib/runtime"

type BatchOutput = {
  id: string
  type: string
  label: string
  status?: string
  prompt?: string
  artifact_data_url?: string
  error?: string
  title: string
  filename?: string
}

type BatchAnchor = {
  product_name_en?: string
  product_name_zh?: string
  primary_category?: string
  visual_attrs?: string[]
  confidence?: number
}

type BatchPreviewResponse = {
  image_model: string
  analysis_model?: string
  title_model: string
  provider?: string
  execution_mode?: string
  upload_count?: number
  reference_count: number
  total_outputs: number
  brief_summary: string
  anchor?: BatchAnchor
  outputs: BatchOutput[]
  titles?: string[]
  title_warnings?: string[]
  errors?: string[]
}

const imageTypes = [
  { value: "main", label: "主图白底" },
  { value: "feature", label: "功能卖点" },
  { value: "scene", label: "场景应用" },
  { value: "detail", label: "细节特写" },
  { value: "size", label: "尺寸规格" },
  { value: "compare", label: "对比优势" },
  { value: "package", label: "清单展示" },
  { value: "steps", label: "使用步骤" },
]

const maxUploadCount = 6
const maxUploadSizeBytes = 7 * 1024 * 1024

type BatchWorkspaceProps = {
  apiBaseUrl: string
  currentProject?: RuntimePayload["current_project"]
}

function isSupportedImageFile(file: File) {
  return (
    [
      "image/png",
      "image/jpeg",
      "image/jpg",
      "image/webp",
      "image/heic",
      "image/heif",
    ].includes(file.type.toLowerCase()) || /\.(png|jpe?g|webp|heic|heif)$/i.test(file.name)
  )
}

function formatFileSize(sizeBytes: number) {
  if (sizeBytes >= 1024 * 1024) {
    return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
  }
  if (sizeBytes >= 1024) {
    return `${Math.round(sizeBytes / 1024)} KB`
  }
  return `${sizeBytes} B`
}

function readFileAsDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result)
        return
      }
      reject(new Error(`文件 ${file.name} 读取失败，请重新选择。`))
    }
    reader.onerror = () => {
      reject(new Error(`文件 ${file.name} 读取失败，请重新选择。`))
    }
    reader.readAsDataURL(file)
  })
}

function fallbackDownloadName(item: BatchOutput) {
  const filename = item.filename?.trim()
  if (filename) {
    return filename.toLowerCase().endsWith(".png") ? filename : `${filename}.png`
  }

  const label = item.label.trim().replace(/\s+/g, "-")
  return `${label || item.id || "batch-output"}.png`
}

function formatConfidence(value?: number) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "未返回"
  }
  if (value <= 1) {
    return `${Math.round(value * 100)}%`
  }
  return `${Math.round(value)}%`
}

export function BatchWorkspace({ apiBaseUrl, currentProject }: BatchWorkspaceProps) {
  const normalizedApiBaseUrl = useMemo(
    () => apiBaseUrl.replace(/\/$/, ""),
    [apiBaseUrl],
  )
  const taskCenterLabel = currentProject ? "当前项目任务中心" : "任务中心"
  const taskCenterLinkLabel = currentProject ? "查看当前项目任务" : "查看任务中心"
  const [uploadItems, setUploadItems] = useState<ImageUploadItem[]>([])
  const [uploadError, setUploadError] = useState("")
  const [productInfo, setProductInfo] = useState("")
  const [selectedTypes, setSelectedTypes] = useState<string[]>(["main", "feature"])
  const [includeTitles, setIncludeTitles] = useState(true)
  const [briefNotes, setBriefNotes] = useState("")
  const [result, setResult] = useState<BatchPreviewResponse | null>(null)
  const [jobId, setJobId] = useState("")
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  const zipExportUrl = jobId
    ? buildJobArtifactsZipUrl(normalizedApiBaseUrl, jobId)
    : ""

  function toggleType(value: string) {
    setSelectedTypes((current) => {
      if (current.includes(value)) {
        return current.filter((item) => item !== value)
      }
      return [...current, value].slice(0, 6)
    })
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    setResult(null)
    setJobId("")

    if (uploadItems.length === 0 && !productInfo.trim()) {
      setError("请先上传 1-6 张商品图片，或补充商品说明后再生成批量出图。")
      return
    }

    if (selectedTypes.length === 0) {
      setError("请至少选择一种出图类型。")
      return
    }

    setIsSubmitting(true)

    try {
      const queuedJob = await submitAsyncJob(normalizedApiBaseUrl, {
        task_type: "batch_generation",
        summary: `批量出图 · ${selectedTypes.length} 种类型${uploadItems.length > 0 ? ` · ${uploadItems.length} 张商品图` : ""}`,
        payload: {
          productInfo,
          selectedTypes,
          includeTitles,
          briefNotes,
          ...(uploadItems.length > 0
            ? {
                uploadItems,
                referenceCount: uploadItems.length,
              }
            : {}),
        },
      })
      setJobId(queuedJob.job.id)
      const completedJob = await waitForJobCompletion(
        normalizedApiBaseUrl,
        queuedJob.job.id,
        { intervalMs: 1000, timeoutMs: 180000 },
      )
      if (completedJob.status === "failed") {
        throw new Error(String(completedJob.result?.error || "批量出图暂时不可用，请稍后重试。"))
      }
      setResult(completedJob.result as BatchPreviewResponse)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "批量出图暂时不可用，请稍后重试。",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleUploadChange(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files || [])
    event.target.value = ""

    if (files.length === 0) {
      return
    }

    if (files.length > maxUploadCount) {
      setUploadError(`当前最多上传 ${maxUploadCount} 张图片，请精简后再试。`)
      return
    }

    const invalidFile = files.find((file) => !isSupportedImageFile(file))
    if (invalidFile) {
      setUploadError(`文件 ${invalidFile.name} 不是支持的图片格式，请改为 PNG、JPG、WEBP、HEIC 或 HEIF。`)
      return
    }

    const oversizedFile = files.find((file) => file.size > maxUploadSizeBytes)
    if (oversizedFile) {
      setUploadError(`文件 ${oversizedFile.name} 超过 7MB 限制，请压缩后重试。`)
      return
    }

    try {
      const nextItems = await Promise.all(
        files.map(async (file, index) => ({
          id: `batch-${Date.now()}-${index + 1}`,
          rawName: file.name,
          mimeType: file.type || "image/png",
          sizeBytes: file.size,
          imageDataUrl: await readFileAsDataUrl(file),
        })),
      )
      setUploadItems(nextItems)
      setUploadError("")
    } catch (requestError) {
      setUploadError(
        requestError instanceof Error
          ? requestError.message
          : "图片读取失败，请重新选择。",
      )
    }
  }

  function removeUploadItem(uploadId: string) {
    setUploadItems((current) => current.filter((item) => item.id !== uploadId))
  }

  return (
    <section className="grid gap-6 xl:grid-cols-[1.12fr_0.88fr]">
      <form
        onSubmit={handleSubmit}
        className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <h3 className="text-2xl font-bold text-slate-950">批量出图工作区</h3>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          当前会优先按上传商品图建立批次参考，再按所选类型提交真实批量出图任务；商品说明仅作为补充信息，用来帮助系统理解品类与重点。
        </p>
        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          {currentProject ? (
            <p>
              <span className="font-medium text-slate-900">当前项目：</span>
              {currentProject.project_name} · {currentProject.project_slug}
            </p>
          ) : (
            <p>未检测到当前项目，服务端会在提交时继续校验项目上下文。</p>
          )}
        </div>

        <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-slate-900">商品图片上传（1-6 张）</p>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                上传图片后会直接参与批量出图锚点分析与参考图构建；若没有图片，也可以先用商品说明走简化批次链路。
              </p>
            </div>
            <label className="inline-flex cursor-pointer rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50">
              选择图片
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={handleUploadChange}
                className="sr-only"
              />
            </label>
          </div>

          <div className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-3 text-sm leading-6 text-slate-500">
            如需上传，请选择 1-6 张商品图。支持 PNG、JPG、WEBP、HEIC、HEIF，单张不超过 7MB。
          </div>

          {uploadItems.length > 0 ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {uploadItems.map((item) => (
                <div key={item.id} className="rounded-2xl border border-slate-200 bg-white p-3">
                  <img
                    src={item.imageDataUrl}
                    alt={item.rawName}
                    className="h-28 w-full rounded-2xl border border-slate-200 object-cover"
                  />
                  <div className="mt-3 flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-900">{item.rawName}</p>
                      <p className="mt-1 text-xs text-slate-500">{formatFileSize(item.sizeBytes)}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeUploadItem(item.id)}
                      className="rounded-xl border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 transition hover:border-sky-300 hover:bg-sky-50"
                    >
                      移除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          {uploadError ? (
            <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {uploadError}
            </div>
          ) : null}
        </div>

        <label className="mt-6 block text-sm font-medium text-slate-800">
          商品补充说明（可选）
          <textarea
            value={productInfo}
            onChange={(event) => setProductInfo(event.target.value)}
            rows={5}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            placeholder="例如：Foldable camping chair with cup holder, lightweight aluminum frame, outdoor portable design"
          />
          <span className="mt-2 block text-xs font-normal leading-6 text-slate-500">
            已上传商品图时可留空；这里更适合补充英文品名、使用场景、规格或视觉重点。
          </span>
        </label>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            <p className="font-medium text-slate-900">已选类型</p>
            <p className="mt-1">{selectedTypes.length} / 6 种</p>
            <p className="mt-1 text-xs leading-6 text-slate-500">保持当前的一键品类逻辑，只移除手工填写的伪参考图数量。</p>
          </div>

          <label className="block text-sm font-medium text-slate-800">
            标题联动
            <div className="mt-2 flex h-[78px] items-center rounded-2xl border border-slate-200 px-4 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={includeTitles}
                onChange={(event) => setIncludeTitles(event.target.checked)}
                className="mr-3 h-4 w-4 rounded border-slate-300"
              />
              同时生成标题候选
            </div>
          </label>
        </div>

        <div className="mt-4">
          <p className="text-sm font-medium text-slate-800">出图类型</p>
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            {imageTypes.map((item) => {
              const active = selectedTypes.includes(item.value)
              return (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => toggleType(item.value)}
                  className={`rounded-2xl border px-4 py-3 text-left text-sm transition ${
                    active
                      ? "border-sky-400 bg-sky-50 text-sky-800"
                      : "border-slate-200 bg-white text-slate-700 hover:border-sky-300"
                  }`}
                >
                  {item.label}
                </button>
              )
            })}
          </div>
        </div>

        <label className="mt-4 block text-sm font-medium text-slate-800">
          图需摘要（可选）
          <textarea
            value={briefNotes}
            onChange={(event) => setBriefNotes(event.target.value)}
            rows={3}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            placeholder="例如：突出户外露营场景、清爽背景、兼顾便携和承重卖点。"
          />
        </label>

        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-6 rounded-2xl bg-sky-600 px-5 py-3 text-sm font-medium text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {isSubmitting ? "生成中..." : "生成批量出图"}
        </button>

        {error ? (
          <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        {jobId ? (
          <div className="mt-4 rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-700">
            已写入{taskCenterLabel}：`{jobId}`。<Link href="/tasks" className="font-semibold underline">{taskCenterLinkLabel}</Link>
          </div>
        ) : null}
      </form>

      <div className="space-y-6">
        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-xl font-bold text-slate-950">批量方案摘要</h3>
            {result ? (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {result.total_outputs} 个输出
              </span>
            ) : null}
          </div>

          {result ? (
            <div className="mt-4 space-y-4 text-sm leading-7 text-slate-600">
              <div className="space-y-3">
                <p>执行 Provider：{result.provider || "system"}</p>
                <p>图片模型：{result.image_model}</p>
                {result.analysis_model ? <p>分析模型：{result.analysis_model}</p> : null}
                <p>标题模型：{result.title_model}</p>
                <p>执行模式：{result.execution_mode || "text"}</p>
                <p>已上传商品图：{result.upload_count ?? uploadItems.length}</p>
                <p>参与参考：{result.reference_count}</p>
                <p>图需摘要：{result.brief_summary}</p>
              </div>

              {result.anchor ? (
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-sm font-semibold text-slate-900">批次锚点摘要</p>
                  <div className="mt-3 space-y-2">
                    <p>英文品名：{result.anchor.product_name_en || "未返回"}</p>
                    <p>中文品名：{result.anchor.product_name_zh || "未返回"}</p>
                    <p>主类目：{result.anchor.primary_category || "未返回"}</p>
                    <p>置信度：{formatConfidence(result.anchor.confidence)}</p>
                    <div>
                      <p className="text-sm text-slate-900">视觉属性</p>
                      {result.anchor.visual_attrs && result.anchor.visual_attrs.length > 0 ? (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {result.anchor.visual_attrs.map((item, index) => (
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
              ) : null}
            </div>
          ) : (
            <p className="mt-4 text-sm leading-7 text-slate-500">
              当前页面会优先使用上传商品图建立批次锚点，并按多个目标类型生成真实结果；如果浏览器等待超时，请直接去{taskCenterLabel}继续查看任务进度。
            </p>
          )}
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-xl font-bold text-slate-950">输出结果</h3>
            {result && zipExportUrl ? (
              <a
                href={zipExportUrl}
                className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50"
              >
                导出 ZIP
              </a>
            ) : null}
          </div>
          {result ? (
            <div className="mt-4 space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                {result.outputs.map((item) => (
                  <div key={item.id} className="rounded-2xl border border-slate-200 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{item.label}</p>
                        {item.filename ? (
                          <p className="mt-1 text-xs text-slate-500">{item.filename}</p>
                        ) : null}
                      </div>
                      {item.status ? (
                        <p className={`text-xs font-medium ${item.status === "failed" ? "text-rose-600" : "text-slate-500"}`}>
                          {item.status === "completed" ? "已完成" : item.status === "failed" ? "失败" : item.status}
                        </p>
                      ) : null}
                    </div>
                    {item.artifact_data_url ? (
                      <img
                        src={item.artifact_data_url}
                        alt={item.label}
                        className="mt-3 w-full rounded-2xl border border-slate-200 object-cover"
                      />
                    ) : null}
                    {item.prompt ? (
                      <p className="mt-2 text-sm leading-6 text-slate-500">{item.prompt}</p>
                    ) : null}
                    {item.title ? (
                      <p className="mt-3 text-sm text-slate-700">标题候选：{item.title}</p>
                    ) : null}
                    {item.artifact_data_url ? (
                      <a
                        href={item.artifact_data_url}
                        download={fallbackDownloadName(item)}
                        className="mt-3 inline-flex rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50"
                      >
                        下载 PNG
                      </a>
                    ) : null}
                    {item.error ? (
                      <p className="mt-2 text-sm leading-6 text-rose-600">{item.error}</p>
                    ) : null}
                  </div>
                ))}
              </div>

              {result.titles && result.titles.length > 0 ? (
                <div>
                  <p className="text-sm font-semibold text-slate-900">批次标题候选</p>
                  <div className="mt-3 space-y-2">
                    {result.titles.map((title, index) => (
                      <div key={`${title}-${index}`} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-700">
                        {index + 1}. {title}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {result.title_warnings && result.title_warnings.length > 0 ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                  {result.title_warnings.map((warning, index) => (
                    <p key={`${warning}-${index}`}>{warning}</p>
                  ))}
                </div>
              ) : null}

              {result.errors && result.errors.length > 0 ? (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  {result.errors.map((entry, index) => (
                    <p key={`${entry}-${index}`}>{entry}</p>
                  ))}
                </div>
              ) : null}
            </div>
          ) : (
            <p className="mt-4 text-sm leading-7 text-slate-500">
              提交后这里会显示真实批量结果、批次锚点摘要，并支持逐张下载 PNG 或直接导出 ZIP；若浏览器等待超时，请直接去{taskCenterLabel}继续查看任务进度。
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
