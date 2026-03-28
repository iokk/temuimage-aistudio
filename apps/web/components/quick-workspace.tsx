"use client"

import Link from "next/link"
import { useMemo, useState, type FormEvent } from "react"

import { submitAsyncJob, waitForJobCompletion } from "../lib/job-client"

type QuickPreviewResponse = {
  image_model: string
  title_model: string
  prompt_summary: string
  outputs: Array<{
    id: string
    label: string
    preview_text: string
  }>
  titles: string[]
}

const imageTypes = [
  { value: "main_visual", label: "主图强化" },
  { value: "detail_card", label: "卖点细节图" },
  { value: "scene_banner", label: "场景横幅图" },
]

export function QuickWorkspace({ apiBaseUrl }: { apiBaseUrl: string }) {
  const normalizedApiBaseUrl = useMemo(
    () => apiBaseUrl.replace(/\/$/, ""),
    [apiBaseUrl],
  )
  const [productInfo, setProductInfo] = useState("")
  const [imageType, setImageType] = useState("main_visual")
  const [count, setCount] = useState(4)
  const [includeTitles, setIncludeTitles] = useState(true)
  const [styleNotes, setStyleNotes] = useState("")
  const [result, setResult] = useState<QuickPreviewResponse | null>(null)
  const [error, setError] = useState("")
  const [jobId, setJobId] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    setResult(null)
    setJobId("")

    if (!productInfo.trim()) {
      setError("请先输入商品信息，再生成快速出图预览。")
      return
    }

    setIsSubmitting(true)

    try {
      const queuedJob = await submitAsyncJob(normalizedApiBaseUrl, {
        task_type: "quick_generation",
        summary: `快速出图 · ${imageType} · ${count} 张`,
        payload: {
          productInfo,
          imageType,
          count,
          includeTitles,
          styleNotes,
        },
      })
      setJobId(queuedJob.job.id)
      const completedJob = await waitForJobCompletion(
        normalizedApiBaseUrl,
        queuedJob.job.id,
      )
      if (completedJob.status === "failed") {
        throw new Error(String(completedJob.result?.error || "快速出图预览接口暂时不可用，请稍后重试。"))
      }
      setResult(completedJob.result as QuickPreviewResponse)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "快速出图预览接口暂时不可用，请稍后重试。",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr]">
      <form
        onSubmit={handleSubmit}
        className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <h3 className="text-2xl font-bold text-slate-950">快速出图工作区</h3>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          保持少步骤：输入商品信息、选择图片类型、决定是否带标题，然后直接拿到预览结果和任务记录。
        </p>

        <label className="mt-6 block text-sm font-medium text-slate-800">
          商品信息
          <textarea
            value={productInfo}
            onChange={(event) => setProductInfo(event.target.value)}
            rows={7}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            placeholder="例如：Portable blender for smoothies, USB rechargeable, compact for travel and office use"
          />
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
          风格补充
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
          {isSubmitting ? "生成中..." : "生成快速出图预览"}
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
            <h3 className="text-xl font-bold text-slate-950">当前接通状态</h3>
            {result ? (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {result.image_model}
              </span>
            ) : null}
          </div>
          {result ? (
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
              <p>图片模型：{result.image_model}</p>
              <p>标题模型：{result.title_model}</p>
              <p>图需摘要：{result.prompt_summary}</p>
            </div>
          ) : (
            <p className="mt-4 text-sm leading-7 text-slate-500">
              当前阶段先接通快速出图预览、标题开关和任务中心。后续再补真实上传素材与生成图片缩略图。
            </p>
          )}
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h3 className="text-xl font-bold text-slate-950">预览结果</h3>
          {result ? (
            <div className="mt-4 space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                {result.outputs.map((item) => (
                  <div key={item.id} className="rounded-2xl border border-slate-200 p-4">
                    <p className="text-sm font-semibold text-slate-900">{item.label}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-500">{item.preview_text}</p>
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
            </div>
          ) : (
            <p className="mt-4 text-sm leading-7 text-slate-500">
              提交后这里会先返回结构化出图预览卡片，作为后续真实图片生成链路的承接面板。
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
