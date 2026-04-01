"use client"

import { useMemo, useState, type FormEvent } from "react"

import type { SystemExecutionConfigPayload } from "../lib/runtime"

type Props = {
  apiBaseUrl: string
  initialConfig: SystemExecutionConfigPayload | null
}

type FormState = {
  title_model: string
  translate_provider: string
  translate_image_model: string
  translate_analysis_model: string
  quick_image_model: string
  batch_image_model: string
  relay_api_base: string
  relay_api_key: string
  relay_default_image_model: string
  gemini_api_key: string
}

function buildInitialState(config: SystemExecutionConfigPayload | null): FormState {
  return {
    title_model: config?.title_model || "gemini-3.1-pro",
    translate_provider: config?.translate_provider || "gemini",
    translate_image_model: config?.translate_image_model || "gemini-3.1-flash-image-preview",
    translate_analysis_model: config?.translate_analysis_model || "gemini-3.1-pro",
    quick_image_model: config?.quick_image_model || "gemini-3.1-flash-image-preview",
    batch_image_model: config?.batch_image_model || "gemini-3.1-flash-image-preview",
    relay_api_base: config?.relay_api_base || "",
    relay_api_key: "",
    relay_default_image_model: config?.relay_default_image_model || "gemini-3.1-flash-image-preview",
    gemini_api_key: "",
  }
}

export function AdminConfigPanel({ apiBaseUrl, initialConfig }: Props) {
  const normalizedApiBaseUrl = useMemo(
    () => apiBaseUrl.replace(/\/$/, ""),
    [apiBaseUrl],
  )
  const [form, setForm] = useState<FormState>(() => buildInitialState(initialConfig))
  const [configMeta, setConfigMeta] = useState(() => ({
    source: initialConfig?.source || "environment",
    persistenceEnabled: initialConfig?.persistence_enabled || false,
    relayApiKeyPreview: initialConfig?.relay_api_key_preview || "未配置",
    geminiApiKeyPreview: initialConfig?.gemini_api_key_preview || "未配置",
  }))
  const [statusText, setStatusText] = useState("")
  const [error, setError] = useState("")
  const [isSaving, setIsSaving] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    setStatusText("")
    setIsSaving(true)

    try {
      const response = await fetch(`${normalizedApiBaseUrl}/system/config`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      })

      if (!response.ok) {
        throw new Error("系统配置保存失败，请稍后重试。")
      }

      const payload = (await response.json()) as SystemExecutionConfigPayload
      setForm(buildInitialState(payload))
      setConfigMeta({
        source: payload.source,
        persistenceEnabled: payload.persistence_enabled,
        relayApiKeyPreview: payload.relay_api_key_preview || "未配置",
        geminiApiKeyPreview: payload.gemini_api_key_preview || "未配置",
      })
      setStatusText(
        payload.persistence_enabled
          ? `已保存，当前配置源：${payload.source}`
          : `已保存到当前进程内存，重启后需要重新设置。`,
      )
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "系统配置保存失败，请稍后重试。",
      )
    } finally {
      setIsSaving(false)
    }
  }

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-xl font-bold text-slate-950">系统执行配置</h3>
          <p className="mt-3 text-sm leading-7 text-slate-600">
            这一组配置会作为标题、翻译、快速出图、批量出图的统一系统默认值。后续四条真实执行链都会优先读取这里。
          </p>
        </div>
        <div className="rounded-2xl bg-slate-100 px-4 py-2 text-xs font-medium text-slate-600">
          当前来源：{configMeta.source}
        </div>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <label className="block text-sm font-medium text-slate-800">
          标题模型
          <input
            value={form.title_model}
            onChange={(event) => updateField("title_model", event.target.value)}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
          />
        </label>

        <label className="block text-sm font-medium text-slate-800">
          翻译 Provider
          <select
            value={form.translate_provider}
            onChange={(event) => updateField("translate_provider", event.target.value)}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
          >
            <option value="gemini">gemini</option>
            <option value="relay">relay</option>
          </select>
        </label>

        <label className="block text-sm font-medium text-slate-800">
          翻译图像模型
          <input
            value={form.translate_image_model}
            onChange={(event) => updateField("translate_image_model", event.target.value)}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
          />
        </label>

        <label className="block text-sm font-medium text-slate-800">
          翻译分析模型
          <input
            value={form.translate_analysis_model}
            onChange={(event) => updateField("translate_analysis_model", event.target.value)}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
          />
        </label>

        <label className="block text-sm font-medium text-slate-800">
          快速出图模型
          <input
            value={form.quick_image_model}
            onChange={(event) => updateField("quick_image_model", event.target.value)}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
          />
        </label>

        <label className="block text-sm font-medium text-slate-800">
          批量出图模型
          <input
            value={form.batch_image_model}
            onChange={(event) => updateField("batch_image_model", event.target.value)}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
          />
        </label>

        <label className="block text-sm font-medium text-slate-800 lg:col-span-2">
          中转站 API Base
          <input
            value={form.relay_api_base}
            onChange={(event) => updateField("relay_api_base", event.target.value)}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            placeholder="https://example.com/v1"
          />
        </label>

        <label className="block text-sm font-medium text-slate-800">
          中转站默认图片模型
          <input
            value={form.relay_default_image_model}
            onChange={(event) => updateField("relay_default_image_model", event.target.value)}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
          />
        </label>

        <label className="block text-sm font-medium text-slate-800">
          Gemini API Key
          <input
            type="password"
            value={form.gemini_api_key}
            onChange={(event) => updateField("gemini_api_key", event.target.value)}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            placeholder={configMeta.geminiApiKeyPreview}
          />
        </label>

        <label className="block text-sm font-medium text-slate-800 lg:col-span-2">
          中转站 API Key
          <input
            type="password"
            value={form.relay_api_key}
            onChange={(event) => updateField("relay_api_key", event.target.value)}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
            placeholder={configMeta.relayApiKeyPreview}
          />
        </label>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={isSaving}
          className="rounded-2xl bg-sky-600 px-5 py-3 text-sm font-medium text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {isSaving ? "保存中..." : "保存系统配置"}
        </button>
        <p className="text-sm text-slate-500">
          {configMeta.persistenceEnabled
            ? "当前环境支持持久化配置。"
            : "当前环境未接数据库持久化，保存后仅在当前进程内有效。"}
        </p>
      </div>

      {statusText ? (
        <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {statusText}
        </div>
      ) : null}

      {error ? (
        <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}
    </form>
  )
}
