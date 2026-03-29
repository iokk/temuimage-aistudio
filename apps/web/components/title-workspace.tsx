"use client"

import Link from "next/link"
import { useMemo, useState, type FormEvent } from "react"

import { submitAsyncJob, waitForJobCompletion } from "../lib/job-client"

type PreviewResponse = {
  titles: string[]
  model: string
  source: string
}

const tones = [
  { value: "marketplace", label: "平台常规" },
  { value: "premium", label: "偏高级感" },
  { value: "clean", label: "偏简洁" },
]

export function TitleWorkspace({ apiBaseUrl }: { apiBaseUrl: string }) {
  const normalizedApiBaseUrl = useMemo(
    () => apiBaseUrl.replace(/\/$/, ""),
    [apiBaseUrl],
  )
  const [productInfo, setProductInfo] = useState("")
  const [extraRequirements, setExtraRequirements] = useState("")
  const [tone, setTone] = useState("marketplace")
  const [count, setCount] = useState(3)
  const [result, setResult] = useState<PreviewResponse | null>(null)
  const [jobId, setJobId] = useState("")
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    setResult(null)
    setJobId("")

    if (!productInfo.trim()) {
      setError("请先输入商品信息，再生成标题预览。")
      return
    }

    setIsSubmitting(true)

    try {
      const queuedJob = await submitAsyncJob(normalizedApiBaseUrl, {
        task_type: "title_generation",
        summary: `标题预览 · ${tone} · ${count} 条候选`,
        payload: {
          productInfo,
          extraRequirements,
          tone,
          count,
        },
      })
      setJobId(queuedJob.job.id)
      const completedJob = await waitForJobCompletion(
        normalizedApiBaseUrl,
        queuedJob.job.id,
      )
      if (completedJob.status === "failed") {
        throw new Error(String(completedJob.result?.error || "标题预览接口暂时不可用，请稍后重试。"))
      }
      setResult(completedJob.result as PreviewResponse)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "标题预览接口暂时不可用，请稍后重试。",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
      <form
        onSubmit={handleSubmit}
        className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <h3 className="text-2xl font-bold text-slate-950">标题优化工作区</h3>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          先接通新栈里的标题预览接口。当前版本使用稳定的预览逻辑返回多条候选标题，后续再切到真实模型与任务链路。
        </p>

        <label className="mt-6 block text-sm font-medium text-slate-800">
          商品信息
          <textarea
            value={productInfo}
            onChange={(event) => setProductInfo(event.target.value)}
            rows={7}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            placeholder="例如：Women running shoes breathable mesh lightweight casual sneaker for daily walking"
          />
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

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
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
          disabled={isSubmitting}
          className="mt-6 rounded-2xl bg-sky-600 px-5 py-3 text-sm font-medium text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {isSubmitting ? "生成中..." : "生成标题预览"}
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
          <h3 className="text-xl font-bold text-slate-950">当前接通状态</h3>
          <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
            <p>页面已接到新 FastAPI 的 `/v1/title/preview`。</p>
            <p>标题模型默认使用 `gemini-3.1-pro`。</p>
            <p>下一步会把图片输入、真实模型调用和任务中心串起来。</p>
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-xl font-bold text-slate-950">候选标题</h3>
            {result ? (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {result.model}
              </span>
            ) : null}
          </div>

          {result ? (
            <div className="mt-4 space-y-3">
              {result.titles.map((title, index) => (
                <div
                  key={`${title}-${index}`}
                  className="rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-800"
                >
                  {index + 1}. {title}
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm leading-7 text-slate-500">
              提交商品信息后，这里会返回多条英文标题候选，作为后续真实标题优化链路的第一版交互面板。
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
