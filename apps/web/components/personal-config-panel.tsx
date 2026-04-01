"use client"

import { useMemo, useState, type FormEvent } from "react"

import type { PersonalExecutionConfigPayload, RuntimePayload } from "../lib/runtime"

type Props = {
  apiBaseUrl: string
  currentProject?: RuntimePayload["current_project"] | null
  initialConfig: PersonalExecutionConfigPayload | null
}

type FormState = {
  use_personal_credentials: boolean
  provider: string
  relay_api_base: string
  relay_api_key: string
  relay_default_image_model: string
  gemini_api_key: string
}

function buildInitialState(config: PersonalExecutionConfigPayload | null): FormState {
  return {
    use_personal_credentials: config?.use_personal_credentials || false,
    provider: config?.provider || "gemini",
    relay_api_base: config?.relay_api_base || "",
    relay_api_key: "",
    relay_default_image_model: config?.relay_default_image_model || "gemini-3.1-flash-image-preview",
    gemini_api_key: "",
  }
}

export function PersonalConfigPanel({ apiBaseUrl, currentProject, initialConfig }: Props) {
  const normalizedApiBaseUrl = useMemo(() => apiBaseUrl.replace(/\/$/, ""), [apiBaseUrl])
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

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    setStatusText("")
    setIsSaving(true)

    try {
      const response = await fetch(`${normalizedApiBaseUrl}/personal/config`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      })

      if (!response.ok) {
        throw new Error("个人执行配置保存失败，请稍后重试。")
      }

      const payload = (await response.json()) as PersonalExecutionConfigPayload
      setForm(buildInitialState(payload))
      setConfigMeta({
        source: payload.source,
        persistenceEnabled: payload.persistence_enabled,
        relayApiKeyPreview: payload.relay_api_key_preview || "未配置",
        geminiApiKeyPreview: payload.gemini_api_key_preview || "未配置",
      })
      setStatusText(
        payload.persistence_enabled
          ? `已保存个人配置，当前来源：${payload.source}`
          : "已保存到当前进程内存，重启后需要重新设置。",
      )
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "个人执行配置保存失败，请稍后重试。",
      )
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-xl font-bold text-slate-950">当前个人执行配置</h3>
          <p className="mt-3 text-sm leading-7 text-slate-600">
            登录个人模式后，可以在这里配置自己的 Gemini Key 或个人中转站。开启后，标题、翻译、快速出图、批量出图都会优先读取你的个人凭据。
          </p>
        </div>
        <div className="rounded-2xl bg-slate-100 px-4 py-2 text-xs font-medium text-slate-600">
          当前来源：{configMeta.source}
        </div>
      </div>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        <p>
          当前个人项目：{currentProject?.project_name || "Personal Workspace"}
          {currentProject?.project_slug ? ` · ${currentProject.project_slug}` : ""}
        </p>
      </div>

      <label className="mt-6 flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={form.use_personal_credentials}
          onChange={(event) => updateField("use_personal_credentials", event.target.checked)}
          className="h-4 w-4 rounded border-slate-300"
        />
        提交工作台任务时优先使用我的个人执行凭据
      </label>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <label className="block text-sm font-medium text-slate-800">
          个人 Provider
          <select
            value={form.provider}
            onChange={(event) => updateField("provider", event.target.value)}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400"
          >
            <option value="gemini">gemini</option>
            <option value="relay">relay</option>
          </select>
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
          个人中转站 API Base
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
          {isSaving ? "保存中..." : "保存个人配置"}
        </button>
        <p className="text-sm text-slate-500">
          {configMeta.persistenceEnabled
            ? "当前环境支持持久化个人配置。"
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
