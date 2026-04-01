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

type QuickPreviewResponse = {
  image_model: string
  title_model: string
  provider?: string
  prompt_summary: string
  execution_mode?: string
  upload_count?: number
  reference_count?: number
  image_type?: string
  outputs: Array<{
    id: string
    label: string
    status?: string
    prompt?: string
    artifact_data_url?: string
    filename?: string
    error?: string
  }>
  titles: string[]
  title_warnings?: string[]
  errors?: string[]
}

const imageTypes = [
  { value: "selling_point", label: "卖点图" },
  { value: "scene", label: "场景图" },
  { value: "detail", label: "细节图" },
  { value: "comparison", label: "对比图" },
  { value: "spec", label: "规格图" },
]

const maxUploadCount = 6
const maxUploadSizeBytes = 7 * 1024 * 1024

type QuickWorkspaceProps = {
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

function fallbackDownloadName(item: QuickPreviewResponse["outputs"][number]) {
  const filename = item.filename?.trim()
  if (filename) {
    return filename.toLowerCase().endsWith(".png") ? filename : `${filename}.png`
  }

  const label = item.label.trim().replace(/\s+/g, "-")
  return `${label || item.id || "quick-output"}.png`
}

export function QuickWorkspace({ apiBaseUrl, currentProject }: QuickWorkspaceProps) {
  const normalizedApiBaseUrl = useMemo(
    () => apiBaseUrl.replace(/\/$/, ""),
    [apiBaseUrl],
  )
  const taskCenterLabel = currentProject ? "当前项目任务中心" : "任务中心"
  const taskCenterLinkLabel = currentProject ? "查看当前项目任务" : "查看任务中心"
  const [uploadItems, setUploadItems] = useState<ImageUploadItem[]>([])
  const [uploadError, setUploadError] = useState("")
  const [productInfo, setProductInfo] = useState("")
  const [imageType, setImageType] = useState("selling_point")
  const [count, setCount] = useState(4)
  const [includeTitles, setIncludeTitles] = useState(true)
  const [styleNotes, setStyleNotes] = useState("")
  const [result, setResult] = useState<QuickPreviewResponse | null>(null)
  const [error, setError] = useState("")
  const [jobId, setJobId] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  const zipExportUrl = jobId
    ? buildJobArtifactsZipUrl(normalizedApiBaseUrl, jobId)
    : ""

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    setResult(null)
    setJobId("")

    if (uploadItems.length === 0 && !productInfo.trim()) {
      setError("请先上传 1-6 张商品图片，或补充商品说明后再生成快速出图。")
      return
    }

    setIsSubmitting(true)

    try {
      const imageTypeLabel = imageTypes.find((item) => item.value === imageType)?.label || imageType
      const queuedJob = await submitAsyncJob(normalizedApiBaseUrl, {
        task_type: "quick_generation",
        summary: `快速出图 · ${imageTypeLabel} · ${count} 张${uploadItems.length > 0 ? ` · ${uploadItems.length} 张商品图` : ""}`,
        payload: {
          productInfo,
          imageType,
          count,
          includeTitles,
          styleNotes,
          ...(uploadItems.length > 0 ? { uploadItems } : {}),
        },
      })
      setJobId(queuedJob.job.id)
      const completedJob = await waitForJobCompletion(
        normalizedApiBaseUrl,
        queuedJob.job.id,
        { intervalMs: 1000, timeoutMs: 120000 },
      )
      if (completedJob.status === "failed") {
        throw new Error(String(completedJob.result?.error || "快速出图暂时不可用，请稍后重试。"))
      }
      setResult(completedJob.result as QuickPreviewResponse)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "快速出图暂时不可用，请稍后重试。",
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
          id: `quick-${Date.now()}-${index + 1}`,
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
    <section className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr]">
      <form
        onSubmit={handleSubmit}
        className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <h3 className="text-2xl font-bold text-slate-950">快速出图工作区</h3>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          保持少步骤：先上传 1-6 张商品图，再选择一种目标类型与数量；商品说明改为补充信息，用于给真实出图任务补上下文。
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
                已上传图片会直接作为参考图参与快速出图；如果暂时没有图片，也可以只填写补充说明走简化链路。
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
            placeholder="例如：Portable blender for smoothies, USB rechargeable, compact for travel and office use"
          />
          <span className="mt-2 block text-xs font-normal leading-6 text-slate-500">
            已上传商品图时可留空；若图片信息不足，这里可补充材质、卖点、适用场景等英文说明。
          </span>
        </label>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block text-sm font-medium text-slate-800">
            图片类型
            <select
              value={imageType}
              onChange={(event) => setImageType(event.target.value)}
              className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            >
              {imageTypes.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm font-medium text-slate-800">
            生成数量
            <select
              value={count}
              onChange={(event) => setCount(Number(event.target.value))}
              className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            >
              {[1, 2, 3, 4, 5, 6].map((value) => (
                <option key={value} value={value}>
                  {value} 张
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="mt-4 block text-sm font-medium text-slate-800">
          风格补充（可选）
          <textarea
            value={styleNotes}
            onChange={(event) => setStyleNotes(event.target.value)}
            rows={3}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            placeholder="例如：突出便携、清爽背景、适合 Temu 商品卡风格。"
          />
        </label>

        <label className="mt-4 flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={includeTitles}
            onChange={(event) => setIncludeTitles(event.target.checked)}
            className="h-4 w-4 rounded border-slate-300"
          />
          同时生成标题候选
        </label>

        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-6 rounded-2xl bg-sky-600 px-5 py-3 text-sm font-medium text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {isSubmitting ? "生成中..." : "生成快速出图"}
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
            <h3 className="text-xl font-bold text-slate-950">当前接通状态</h3>
            {result ? (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {result.image_model}
              </span>
            ) : null}
          </div>
          {result ? (
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
              <p>执行 Provider：{result.provider || "system"}</p>
              <p>图片模型：{result.image_model}</p>
              <p>标题模型：{result.title_model}</p>
              <p>执行模式：{result.execution_mode || "text"}</p>
              <p>已上传商品图：{result.upload_count ?? uploadItems.length}</p>
              <p>参与参考：{result.reference_count ?? uploadItems.length}</p>
              <p>图需摘要：{result.prompt_summary}</p>
            </div>
          ) : (
            <p className="mt-4 text-sm leading-7 text-slate-500">
              当前页面会优先使用已上传商品图提交真实出图任务；若浏览器等待超时，请直接去{taskCenterLabel}查看任务进度和最终结果。
            </p>
          )}
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-xl font-bold text-slate-950">出图结果</h3>
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
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                <p>结果数量：{result.outputs.length} 张</p>
                <p>执行类型：{imageTypes.find((item) => item.value === (result.image_type || imageType))?.label || "快速出图"}</p>
              </div>

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

              {result.titles.length > 0 ? (
                <div>
                  <p className="text-sm font-semibold text-slate-900">附带标题</p>
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
                    <p key={`${warning}-${index}`}>- {warning}</p>
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
              提交后这里会显示真实生成结果，并支持逐张下载 PNG 或直接导出 ZIP；若浏览器等待超时，请直接去{taskCenterLabel}查看任务进度和最终结果。
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
