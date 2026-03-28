"use client"

import Link from "next/link"
import { useMemo, useState, type FormEvent } from "react"

import { submitAsyncJob, waitForJobCompletion } from "../lib/job-client"

type BatchOutput = {
  id: string
  type: string
  label: string
  brief: string
  title: string
}

type BatchPreviewResponse = {
  image_model: string
  title_model: string
  reference_count: number
  total_outputs: number
  brief_summary: string
  outputs: BatchOutput[]
}

const imageTypes = [
  { value: "main_visual", label: "主图强化" },
  { value: "detail_card", label: "卖点细节图" },
  { value: "scene_banner", label: "场景横幅图" },
  { value: "comparison_card", label: "对比说明图" },
]

export function BatchWorkspace({ apiBaseUrl }: { apiBaseUrl: string }) {
  const normalizedApiBaseUrl = useMemo(
    () => apiBaseUrl.replace(/\/$/, ""),
    [apiBaseUrl],
  )
  const [productInfo, setProductInfo] = useState("")
  const [selectedTypes, setSelectedTypes] = useState<string[]>(["main_visual", "detail_card"])
  const [referenceCount, setReferenceCount] = useState(2)
  const [includeTitles, setIncludeTitles] = useState(true)
  const [briefNotes, setBriefNotes] = useState("")
  const [result, setResult] = useState<BatchPreviewResponse | null>(null)
  const [jobId, setJobId] = useState("")
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

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

    if (!productInfo.trim()) {
      setError("请先输入商品信息，再生成批量出图预览。")
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
        summary: `批量出图 · ${selectedTypes.length} 种类型 · ${referenceCount} 张参考图`,
        payload: {
          productInfo,
          selectedTypes,
          referenceCount,
          includeTitles,
          briefNotes,
        },
      })
      setJobId(queuedJob.job.id)
      const completedJob = await waitForJobCompletion(
        normalizedApiBaseUrl,
        queuedJob.job.id,
      )
      if (completedJob.status === "failed") {
        throw new Error(String(completedJob.result?.error || "批量出图预览接口暂时不可用，请稍后重试。"))
      }
      setResult(completedJob.result as BatchPreviewResponse)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "批量出图预览接口暂时不可用，请稍后重试。",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="grid gap-6 xl:grid-cols-[1.12fr_0.88fr]">
      <form
        onSubmit={handleSubmit}
        className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <h3 className="text-2xl font-bold text-slate-950">批量出图工作区</h3>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          这里先承接批量出图最核心的几步：商品信息、参考图数量、目标类型、图需摘要，以及是否一起出标题。
        </p>

        <label className="mt-6 block text-sm font-medium text-slate-800">
          商品信息
          <textarea
            value={productInfo}
            onChange={(event) => setProductInfo(event.target.value)}
            rows={7}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            placeholder="例如：Foldable camping chair with cup holder, lightweight aluminum frame, outdoor portable design"
          />
        </label>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block text-sm font-medium text-slate-800">
            参考图数量
            <select
              value={referenceCount}
              onChange={(event) => setReferenceCount(Number(event.target.value))}
              className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            >
              {[1, 2, 3, 4, 5, 6].map((value) => (
                <option key={value} value={value}>
                  {value} 张
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm font-medium text-slate-800">
            标题联动
            <div className="mt-2 flex h-[50px] items-center rounded-2xl border border-slate-200 px-4 text-sm text-slate-700">
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
          图需摘要
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
          {isSubmitting ? "生成中..." : "生成批量出图预览"}
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
            <h3 className="text-xl font-bold text-slate-950">批量方案摘要</h3>
            {result ? (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {result.total_outputs} 个输出
              </span>
            ) : null}
          </div>

          {result ? (
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
              <p>图片模型：{result.image_model}</p>
              <p>标题模型：{result.title_model}</p>
              <p>参考图数量：{result.reference_count}</p>
              <p>图需摘要：{result.brief_summary}</p>
            </div>
          ) : (
            <p className="mt-4 text-sm leading-7 text-slate-500">
              当前阶段先完成“多类型目标 + 图需摘要 + 任务收口”的交互骨架，后续再补真实图片上传、缩略图与批量结果下载。
            </p>
          )}
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h3 className="text-xl font-bold text-slate-950">输出预览</h3>
          {result ? (
            <div className="mt-4 space-y-3">
              {result.outputs.map((item) => (
                <div key={item.id} className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-sm font-semibold text-slate-900">{item.label}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-500">{item.brief}</p>
                  {item.title ? (
                    <p className="mt-3 text-sm text-slate-700">标题候选：{item.title}</p>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm leading-7 text-slate-500">
              提交后这里会显示每种目标类型对应的一张结构化预览卡，作为后续真实批量出图链路的承接面板。
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
