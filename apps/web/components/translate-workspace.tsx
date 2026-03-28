"use client"

import Link from "next/link"
import { useMemo, useState, type FormEvent } from "react"

import { submitAsyncJob, waitForJobCompletion } from "../lib/job-client"

type TranslatePreviewResponse = {
  source_lines: string[]
  translated_lines: string[]
  provider: string
  image_model: string
  analysis_model: string
  provider_message: string
  capability_reasons: string[]
  can_render_output_image: boolean
}

const providerOptions = ["relay", "gemini"]
const imageModelOptions = [
  "seedream-5.0",
  "gemini-3.1-flash-image-preview",
  "seedream-4.6",
]
const analysisModelOptions = [
  "gemini-3.1-flash-lite-preview",
  "gemini-3.1-flash-image-preview",
]

export function TranslateWorkspace({ apiBaseUrl }: { apiBaseUrl: string }) {
  const normalizedApiBaseUrl = useMemo(
    () => apiBaseUrl.replace(/\/$/, ""),
    [apiBaseUrl],
  )
  const [sourceText, setSourceText] = useState("")
  const [sourceLang, setSourceLang] = useState("auto")
  const [targetLang, setTargetLang] = useState("English")
  const [provider, setProvider] = useState("relay")
  const [imageModel, setImageModel] = useState("seedream-5.0")
  const [analysisModel, setAnalysisModel] = useState("gemini-3.1-flash-lite-preview")
  const [result, setResult] = useState<TranslatePreviewResponse | null>(null)
  const [jobId, setJobId] = useState("")
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    setResult(null)
    setJobId("")

    if (!sourceText.trim()) {
      setError("请先输入要翻译的图片文案或 OCR 文本。")
      return
    }

    setIsSubmitting(true)

    try {
      const queuedJob = await submitAsyncJob(normalizedApiBaseUrl, {
        task_type: "image_translate",
        summary: `翻译预览 · ${provider} · ${targetLang}`,
        payload: {
          sourceText,
          sourceLang,
          targetLang,
          provider,
          imageModel,
          analysisModel,
        },
      })
      setJobId(queuedJob.job.id)
      const completedJob = await waitForJobCompletion(
        normalizedApiBaseUrl,
        queuedJob.job.id,
      )
      if (completedJob.status === "failed") {
        throw new Error(String(completedJob.result?.error || "图片翻译预览接口暂时不可用，请稍后重试。"))
      }
      setResult(completedJob.result as TranslatePreviewResponse)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "图片翻译预览接口暂时不可用，请稍后重试。",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
      <form
        onSubmit={handleSubmit}
        className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <h3 className="text-2xl font-bold text-slate-950">图片翻译工作区</h3>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          当前先接通文本预览和模型能力提示。后续再补图片上传、OCR 抽取、译后出图和后台任务链路。
        </p>

        <label className="mt-6 block text-sm font-medium text-slate-800">
          图片文字 / OCR 文本
          <textarea
            value={sourceText}
            onChange={(event) => setSourceText(event.target.value)}
            rows={7}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            placeholder={"例如：\n新款透气运动鞋\n轻便防滑\n适合日常通勤"}
          />
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

        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <label className="block text-sm font-medium text-slate-800">
            Provider
            <select
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
              className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            >
              {providerOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm font-medium text-slate-800">
            图片模型
            <select
              value={imageModel}
              onChange={(event) => setImageModel(event.target.value)}
              className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            >
              {imageModelOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm font-medium text-slate-800">
            分析模型
            <select
              value={analysisModel}
              onChange={(event) => setAnalysisModel(event.target.value)}
              className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            >
              {analysisModelOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-6 rounded-2xl bg-sky-600 px-5 py-3 text-sm font-medium text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {isSubmitting ? "分析中..." : "生成翻译预览"}
        </button>

        {error ? (
          <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        {jobId ? (
          <div className="mt-4 rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-700">
            已写入任务中心：`{jobId}`。<Link href="/tasks" className="font-semibold underline">查看任务中心</Link>
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
            </div>
          ) : (
            <p className="mt-4 text-sm leading-7 text-slate-500">
              这里会明确提示当前 provider / model 是否支持图片翻译出图，避免页面假装可用却在提交后失败。
            </p>
          )}
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h3 className="text-xl font-bold text-slate-950">翻译结果预览</h3>
          {result ? (
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
          ) : (
            <p className="mt-4 text-sm leading-7 text-slate-500">
              提交 OCR 文本后，这里会先显示结构化翻译预览。后续再接图片上传与译后出图结果。
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
