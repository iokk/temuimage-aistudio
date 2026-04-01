"use client"

import Link from "next/link"
import {
  useEffect,
  useMemo,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react"

import {
  submitAsyncJob,
  type ImageUploadItem,
  waitForJobCompletion,
} from "../lib/job-client"
import { TitleReviewResults } from "./title-review-results"
import type { RuntimePayload, TitleContextPayload } from "../lib/runtime"

type PreviewResponse = {
  titles?: string[]
  model: string
  provider?: string
  source: string
  template_key?: string
  template_name?: string
  compliance_mode?: string
  title_pairs?: unknown[]
  execution_mode?: string
  upload_count?: number
  reference_count?: number
  warnings?: string[]
}

const tones = [
  { value: "marketplace", label: "平台常规" },
  { value: "premium", label: "偏高级感" },
  { value: "clean", label: "偏简洁" },
]

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

type TitleWorkspaceProps = {
  apiBaseUrl: string
  currentProject?: RuntimePayload["current_project"]
  titleContext?: TitleContextPayload | null
}

export function TitleWorkspace({ apiBaseUrl, currentProject, titleContext }: TitleWorkspaceProps) {
  const normalizedApiBaseUrl = useMemo(
    () => apiBaseUrl.replace(/\/$/, ""),
    [apiBaseUrl],
  )
  const taskCenterLabel = currentProject ? "当前项目任务中心" : "任务中心"
  const taskCenterLinkLabel = currentProject ? "查看当前项目任务" : "查看任务中心"
  const [uploadItems, setUploadItems] = useState<ImageUploadItem[]>([])
  const [uploadError, setUploadError] = useState("")
  const [productInfo, setProductInfo] = useState("")
  const [extraRequirements, setExtraRequirements] = useState("")
  const [tone, setTone] = useState("marketplace")
  const [count, setCount] = useState(3)
  const [selectedTemplateKey, setSelectedTemplateKey] = useState("")
  const [result, setResult] = useState<PreviewResponse | null>(null)
  const [jobId, setJobId] = useState("")
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const titleWarnings = titleContext?.warnings || []
  const effectiveProject = currentProject || titleContext?.current_project || null
  const isBlocked = !titleContext || !titleContext.ready
  const templateOptions = titleContext?.template_options || []
  const recommendedTemplateKey = uploadItems.length > 0
    ? titleContext?.image_template_key || titleContext?.default_template_key || templateOptions[0]?.key || ""
    : titleContext?.default_template_key || templateOptions[0]?.key || ""
  const selectedTemplate = templateOptions.find((item) => item.key === selectedTemplateKey) || null
  const recommendedTemplate = templateOptions.find((item) => item.key === recommendedTemplateKey) || null

  useEffect(() => {
    setSelectedTemplateKey((current) => {
      if (templateOptions.length === 0) {
        return ""
      }

      if (templateOptions.some((item) => item.key === current)) {
        return current
      }

      return recommendedTemplateKey
    })
  }, [recommendedTemplateKey, templateOptions])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    setResult(null)
    setJobId("")

    if (uploadItems.length === 0 && !productInfo.trim()) {
      setError("请先上传 1-6 张商品图片，或补充商品信息后再生成标题。")
      return
    }

    if (isBlocked) {
      setError(titleContext?.blocking_reason || "标题执行上下文尚未就绪，请先刷新页面后再提交。")
      return
    }

    setIsSubmitting(true)

    try {
      const queuedJob = await submitAsyncJob(normalizedApiBaseUrl, {
        task_type: "title_generation",
        summary: `标题优化 · ${tone} · ${count} 条候选${uploadItems.length > 0 ? ` · ${uploadItems.length} 张商品图` : ""}`,
        payload: {
          productInfo,
          extraRequirements,
          templateKey: selectedTemplateKey || recommendedTemplateKey,
          template_key: selectedTemplateKey || recommendedTemplateKey,
          tone,
          count,
          ...(uploadItems.length > 0 ? { uploadItems } : {}),
        },
      })
      setJobId(queuedJob.job.id)
      const completedJob = await waitForJobCompletion(
        normalizedApiBaseUrl,
        queuedJob.job.id,
        { intervalMs: 1000, timeoutMs: 45000 },
      )
      if (completedJob.status === "failed") {
        throw new Error(String(completedJob.result?.error || "标题生成暂时不可用，请稍后重试。"))
      }
      setResult(completedJob.result as PreviewResponse)
    } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "标题生成暂时不可用，请稍后重试。",
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
          id: `title-${Date.now()}-${index + 1}`,
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
    <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
      <form
        onSubmit={handleSubmit}
        className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <h3 className="text-2xl font-bold text-slate-950">标题优化工作区</h3>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          当前会直接提交真实标题任务，并把执行结果写入任务中心。现在支持只传商品图或图文混合输入；这里返回的是实际模型生成的标题候选，而不是预览样例。
        </p>
        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          <p>
            标题执行状态：
            <span className={titleContext?.ready ? "font-medium text-emerald-700" : "font-medium text-rose-700"}>
              {titleContext?.ready ? "已就绪" : "待修复"}
            </span>
          </p>
          <p>
            有效模型：{titleContext?.default_model || "未返回"}
            {titleContext?.provider ? ` · Provider：${titleContext.provider}` : ""}
          </p>
          <p>配置来源：{titleContext?.config_source || "未返回"}</p>
          {titleContext?.blocking_reason ? <p className="mt-2 text-rose-600">{titleContext.blocking_reason}</p> : null}
        </div>
        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          {effectiveProject ? (
            <p>
              <span className="font-medium text-slate-900">当前项目：</span>
              {effectiveProject.project_name} · {effectiveProject.project_slug}
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
                上传后会直接作为标题生成参考图参与分析；如果还补充商品信息，则会按图文混合模式一起提交。
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
            如需上传，请选择 1-6 张商品图。支持 PNG、JPG、WEBP、HEIC、HEIF，单张不超过 7MB；服务端会按规则使用前 5 张作为有效参考图。
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
          商品信息（可选）
          <textarea
            value={productInfo}
            onChange={(event) => setProductInfo(event.target.value)}
            rows={7}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            placeholder="例如：Women running shoes breathable mesh lightweight casual sneaker for daily walking"
          />
          <span className="mt-2 block text-xs font-normal leading-6 text-slate-500">
            未上传图片时，此处为必填；上传图片后可留空，用于补充材质、卖点、适用场景等英文商品信息。
          </span>
        </label>

        <label className="mt-4 block text-sm font-medium text-slate-800">
          补充要求
          <textarea
            value={extraRequirements}
            onChange={(event) => setExtraRequirements(event.target.value)}
            rows={4}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            placeholder="例如：突出轻便、防滑、适合 Temu/Amazon 风格，避免夸张词。"
          />
        </label>

        <div className="mt-4 grid gap-4 xl:grid-cols-[1.2fr_0.9fr_0.8fr]">
          <label className="block text-sm font-medium text-slate-800">
            标题模板
            <select
              value={selectedTemplateKey}
              onChange={(event) => setSelectedTemplateKey(event.target.value)}
              disabled={templateOptions.length === 0}
              className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400 disabled:bg-slate-50 disabled:text-slate-400"
            >
              {templateOptions.length > 0 ? (
                templateOptions.map((item) => (
                  <option key={item.key} value={item.key}>
                    {item.name}
                  </option>
                ))
              ) : (
                <option value="">未返回模板选项</option>
              )}
            </select>
            <span className="mt-2 block text-xs font-normal leading-6 text-slate-500">
              {selectedTemplate?.desc || "服务端未返回模板说明。"}
              {recommendedTemplate && selectedTemplateKey !== recommendedTemplate.key
                ? ` 当前推荐：${recommendedTemplate.name}。`
                : ""}
            </span>
          </label>

          <label className="block text-sm font-medium text-slate-800">
            风格
            <select
              value={tone}
              onChange={(event) => setTone(event.target.value)}
              className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            >
              {tones.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm font-medium text-slate-800">
            候选数量
            <select
              value={count}
              onChange={(event) => setCount(Number(event.target.value))}
              className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            >
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>
                  {value} 条
                </option>
              ))}
            </select>
          </label>
        </div>

        <button
          type="submit"
          disabled={isSubmitting || isBlocked}
          className="mt-6 rounded-2xl bg-sky-600 px-5 py-3 text-sm font-medium text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {isSubmitting ? "生成中..." : isBlocked ? "请先修复标题配置" : "生成标题"}
        </button>

        {titleWarnings.length > 0 ? (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
            {titleWarnings.map((warning, index) => (
              <p key={`${warning}-${index}`}>- {warning}</p>
            ))}
          </div>
        ) : null}

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
            <h3 className="text-xl font-bold text-slate-950">当前接通状态</h3>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
              <p>页面通过任务中心异步提交真实标题执行任务。</p>
              <p>标题模型会读取当前生效配置，可能来自系统配置或个人配置。</p>
              <p>如果浏览器等待超时，也可以直接去{taskCenterLabel}继续查看结果。</p>
            </div>
          </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-xl font-bold text-slate-950">候选标题</h3>
            {result ? (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {result.provider ? `${result.provider} · ${result.model}` : result.model}
              </span>
            ) : null}
          </div>

          {result ? (
            <>
              <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                <p>执行来源：{result.source || "未返回"}</p>
                <p>执行模式：{result.execution_mode || "未返回"}</p>
                {(result.template_name || result.template_key) ? (
                  <p>
                    标题模板：{result.template_name || "未命名模板"}
                    {result.template_key ? ` · ${result.template_key}` : ""}
                  </p>
                ) : null}
                {result.compliance_mode ? <p>合规模式：{result.compliance_mode}</p> : null}
                <p>已上传商品图：{result.upload_count ?? uploadItems.length}</p>
                <p>参与参考：{result.reference_count ?? Math.min(uploadItems.length, 5)}</p>
              </div>
              <div className="mt-4">
                <TitleReviewResults
                  titlePairsSource={result.title_pairs}
                  fallbackTitlesSource={result.titles}
                  warningsSource={result.warnings}
                  emptyMessage={`提交商品信息、商品图，或两者一起提交后，这里会返回真实模型生成的中英双语标题复核结果。如果任务仍在运行，请到${taskCenterLabel}查看最新状态。`}
                  fallbackHeading="英文标题候选"
                />
              </div>
            </>
          ) : (
            <p className="mt-4 text-sm leading-7 text-slate-500">
              提交商品信息、商品图，或两者一起提交后，这里会返回真实模型生成的标题候选与双语复核结果。如果任务仍在运行，请到{taskCenterLabel}查看最新状态。
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
