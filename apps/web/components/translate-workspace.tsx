"use client"

import Link from "next/link"
import {
  useMemo,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react"

import {
  buildTranslateOutputsZipUrl,
  submitAsyncJob,
  type ImageUploadItem,
  waitForJobCompletion,
} from "../lib/job-client"
import type { RuntimePayload } from "../lib/runtime"

type TranslateOutput = {
  id: string
  label: string
  raw_name?: string
  status?: string
  artifact_data_url?: string
  source_lines: string[]
  translated_lines: string[]
  filename?: string
  error?: string
}

type TranslatePreviewResponse = {
  source_lines: string[]
  translated_lines: string[]
  provider: string
  image_model: string
  analysis_model: string
  provider_message: string
  capability_reasons: string[]
  can_render_output_image: boolean
  execution_mode?: string
  outputs?: TranslateOutput[]
  errors?: string[]
  total_outputs?: number
  completed_outputs?: number
  failed_outputs?: number
}

type TranslateWorkspaceProps = {
  apiBaseUrl: string
  currentProject?: RuntimePayload["current_project"]
}

const maxUploadCount = 6
const maxUploadSizeBytes = 7 * 1024 * 1024

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

function fallbackDownloadName(item: TranslateOutput) {
  const filename = item.filename?.trim()
  if (filename) {
    return filename.toLowerCase().endsWith(".png") ? filename : `${filename}.png`
  }

  const rawName = item.raw_name?.trim().replace(/\.[^/.]+$/, "")
  if (rawName) {
    return `${rawName}-translated.png`
  }

  const label = item.label.trim().replace(/\s+/g, "-")
  return `${label || item.id || "translated-image"}.png`
}

function normalizeOutput(item: TranslateOutput) {
  return {
    ...item,
    source_lines: Array.isArray(item.source_lines) ? item.source_lines : [],
    translated_lines: Array.isArray(item.translated_lines) ? item.translated_lines : [],
  }
}

export function TranslateWorkspace({
  apiBaseUrl,
  currentProject,
}: TranslateWorkspaceProps) {
  const normalizedApiBaseUrl = useMemo(
    () => apiBaseUrl.replace(/\/$/, ""),
    [apiBaseUrl],
  )
  const taskCenterLabel = currentProject ? "当前项目任务中心" : "任务中心"
  const taskCenterLinkLabel = currentProject ? "查看当前项目任务" : "查看任务中心"
  const [sourceText, setSourceText] = useState("")
  const [sourceLang, setSourceLang] = useState("auto")
  const [targetLang, setTargetLang] = useState("English")
  const [uploadItems, setUploadItems] = useState<ImageUploadItem[]>([])
  const [uploadError, setUploadError] = useState("")
  const [result, setResult] = useState<TranslatePreviewResponse | null>(null)
  const [selectedOutputId, setSelectedOutputId] = useState("")
  const [jobId, setJobId] = useState("")
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  const outputs = useMemo(
    () => (result?.outputs || []).map(normalizeOutput),
    [result?.outputs],
  )
  const hasImageBatchResult = result?.execution_mode === "image_batch" && outputs.length > 0
  const selectedOutput = outputs.find((item) => item.id === selectedOutputId) || outputs[0] || null
  const failedOutputs = outputs.filter((item) => item.status === "failed")
  const failedOutputIds = new Set(failedOutputs.map((item) => item.id))
  const failedOutputNames = new Set(
    failedOutputs.map((item) => item.raw_name?.trim() || "").filter(Boolean),
  )
  const retryUploadItems = uploadItems.filter(
    (item) => failedOutputIds.has(item.id) || failedOutputNames.has(item.rawName),
  )
  const zipExportUrl = jobId ? buildTranslateOutputsZipUrl(normalizedApiBaseUrl, jobId) : ""

  async function submitTranslateJob(nextUploadItems: ImageUploadItem[]) {
    setIsSubmitting(true)
    setError("")
    setResult(null)
    setSelectedOutputId("")
    setJobId("")

    try {
      const summaryPrefix = nextUploadItems.length > 0 ? `${nextUploadItems.length} 张图片` : "文本模式"
      const queuedJob = await submitAsyncJob(normalizedApiBaseUrl, {
        task_type: "image_translate",
        summary: `图片翻译 · ${targetLang} · ${summaryPrefix}`,
        payload: {
          sourceText,
          sourceLang,
          targetLang,
          ...(nextUploadItems.length > 0 ? { uploadItems: nextUploadItems } : {}),
        },
      })
      setJobId(queuedJob.job.id)
      const completedJob = await waitForJobCompletion(
        normalizedApiBaseUrl,
        queuedJob.job.id,
        { intervalMs: 1000, timeoutMs: 120000 },
      )
      if (completedJob.status === "failed") {
        throw new Error(String(completedJob.result?.error || "图片翻译暂时不可用，请稍后重试。"))
      }

      const nextResult = completedJob.result as TranslatePreviewResponse
      setResult(nextResult)
      const nextOutputs = (nextResult.outputs || []).map(normalizeOutput)
      setSelectedOutputId(
        nextOutputs.find((item) => item.status === "completed")?.id || nextOutputs[0]?.id || "",
      )
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "图片翻译暂时不可用，请稍后重试。",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (uploadItems.length === 0 && !sourceText.trim()) {
      setError("请先输入要翻译的图片文案或 OCR 文本，或上传 1-6 张图片。")
      return
    }

    await submitTranslateJob(uploadItems)
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
          id: `img-${Date.now()}-${index + 1}`,
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

  async function handleRetryFailedUploads() {
    if (retryUploadItems.length === 0) {
      setError("当前没有可重试的失败图片，请先检查结果列表。")
      return
    }

    await submitTranslateJob(retryUploadItems)
  }

  function removeUploadItem(uploadId: string) {
    setUploadItems((current) => current.filter((item) => item.id !== uploadId))
  }

  return (
    <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
      <form
        onSubmit={handleSubmit}
        className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <h3 className="text-2xl font-bold text-slate-950">图片翻译工作区</h3>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          当前会提交真实翻译任务，并复用管理后台里的统一系统配置。若上传图片，会进入有界图片翻译链路；未上传时，仍保持现有文本翻译路径。
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
              <p className="text-sm font-medium text-slate-900">图片上传（1-6 张）</p>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                上传后会按图片批次返回译后结果、失败项和下载文件；不上传时仍可只走 OCR / 文本翻译。
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
            最少 1 张、最多 6 张。支持 PNG、JPG、WEBP、HEIC、HEIF，单张不超过 7MB；若本轮只想翻译文字，可不上传图片。
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
          图片文字 / OCR 文本
          <textarea
            value={sourceText}
            onChange={(event) => setSourceText(event.target.value)}
            rows={7}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            placeholder={"例如：\n新款透气运动鞋\n轻便防滑\n适合日常通勤"}
          />
          <span className="mt-2 block text-xs font-normal leading-6 text-slate-500">
            未上传图片时，此处为必填；上传图片后可留空，用于文本兜底或补充需要保留的文案。
          </span>
        </label>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block text-sm font-medium text-slate-800">
            来源语言
            <input
              value={sourceLang}
              onChange={(event) => setSourceLang(event.target.value)}
              className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            />
          </label>

          <label className="block text-sm font-medium text-slate-800">
            目标语言
            <input
              value={targetLang}
              onChange={(event) => setTargetLang(event.target.value)}
              className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            />
          </label>
        </div>

        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-7 text-slate-600">
          本页的 Provider、分析模型、图片模型会自动复用系统执行配置。需要切换时，请到管理后台统一修改。
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-2xl bg-sky-600 px-5 py-3 text-sm font-medium text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {isSubmitting ? "翻译中..." : uploadItems.length > 0 ? "生成译后图片结果" : "生成翻译结果"}
          </button>
          {retryUploadItems.length > 0 ? (
            <button
              type="button"
              onClick={() => void handleRetryFailedUploads()}
              disabled={isSubmitting}
              className="rounded-2xl border border-slate-200 px-5 py-3 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400"
            >
              重试失败图片（{retryUploadItems.length}）
            </button>
          ) : null}
          {hasImageBatchResult && zipExportUrl ? (
            <a
              href={zipExportUrl}
              className="rounded-2xl border border-slate-200 px-5 py-3 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50"
            >
              导出 ZIP
            </a>
          ) : null}
        </div>

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
            <h3 className="text-xl font-bold text-slate-950">能力提示</h3>
            {result ? (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {result.provider} / {result.image_model}
              </span>
            ) : null}
          </div>

          {result ? (
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
              <p>{result.provider_message}</p>
              <p>分析模型：{result.analysis_model || "未返回"}</p>
              <p>执行模式：{result.execution_mode || "text"}</p>
              {hasImageBatchResult ? (
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <p>总计：{result.total_outputs || outputs.length} 张</p>
                  <p>成功：{result.completed_outputs ?? outputs.filter((item) => item.status === "completed").length} 张</p>
                  <p>失败：{result.failed_outputs ?? failedOutputs.length} 张</p>
                </div>
              ) : null}
              {result.capability_reasons.length > 0 ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-800">
                  {result.capability_reasons.map((reason, index) => (
                    <p key={`${reason}-${index}`}>{reason}</p>
                  ))}
                </div>
              ) : (
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-700">
                  当前模型组合可继续进入译后出图链路。
                </div>
              )}
              {result.errors && result.errors.length > 0 ? (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-rose-700">
                  {result.errors.map((entry, index) => (
                    <p key={`${entry}-${index}`}>{entry}</p>
                  ))}
                </div>
              ) : null}
            </div>
          ) : (
            <p className="mt-4 text-sm leading-7 text-slate-500">
              这里会显示当前系统配置下的翻译执行能力，避免页面看起来可用，提交后却因为模型能力不匹配而失败。
            </p>
          )}
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-xl font-bold text-slate-950">翻译结果预览</h3>
            {hasImageBatchResult && selectedOutput?.artifact_data_url ? (
              <a
                href={selectedOutput.artifact_data_url}
                download={fallbackDownloadName(selectedOutput)}
                className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50"
              >
                下载当前 PNG
              </a>
            ) : null}
          </div>

          {result ? (
            hasImageBatchResult && selectedOutput ? (
              <div className="mt-4 space-y-4">
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {outputs.map((item) => {
                    const isActive = item.id === selectedOutput.id
                    return (
                      <button
                        key={item.id}
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
                        <p className="mt-1 truncate text-xs text-slate-500">{item.raw_name || fallbackDownloadName(item)}</p>
                      </button>
                    )
                  })}
                </div>

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
              </div>
            ) : (
              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <div>
                  <p className="text-sm font-semibold text-slate-900">原文</p>
                  <div className="mt-3 space-y-2">
                    {result.source_lines.map((line, index) => (
                      <div key={`${line}-${index}`} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-700">
                        {line}
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">译文</p>
                  <div className="mt-3 space-y-2">
                    {result.translated_lines.map((line, index) => (
                      <div key={`${line}-${index}`} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-700">
                        {line}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )
          ) : (
            <p className="mt-4 text-sm leading-7 text-slate-500">
              提交 OCR 文本或图片后，这里会显示真实模型返回的结构化翻译结果。若任务仍在运行，可去{taskCenterLabel}继续查看。
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
