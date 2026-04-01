import "server-only"

import { auth } from "../auth"
import type { JobRecord } from "./job-client"
import type {
  PersonalExecutionConfigPayload,
  RuntimePayload,
  SystemExecutionConfigPayload,
  TitleContextPayload,
} from "./runtime"

function getRemoteApiBaseUrl() {
  return (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "")
}

export async function fetchServerApi(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const session = await auth()
  const accessToken = session?.accessToken

  if (!accessToken) {
    throw new Error("当前登录会话缺少 Casdoor access token。")
  }

  const headers = new Headers(init?.headers)
  headers.set("Authorization", `Bearer ${accessToken}`)

  return fetch(`${getRemoteApiBaseUrl()}/v1${path}`, {
    ...init,
    headers,
    cache: init?.cache ?? "no-store",
  })
}

export async function getServerJob(jobId: string) {
  const response = await fetchServerApi(`/jobs/${jobId}`)

  if (!response.ok) {
    throw new Error("任务详情获取失败，请稍后重试。")
  }

  return (await response.json()) as { job: JobRecord }
}

export async function getServerRuntimePayload(): Promise<RuntimePayload | null> {
  try {
    const response = await fetchServerApi("/system/runtime")
    if (!response.ok) {
      return null
    }
    return (await response.json()) as RuntimePayload
  } catch {
    return null
  }
}

export async function getServerReadinessPayload(): Promise<{
  status: string
  blocking_warnings: string[]
  ready_for_distributed_workers: boolean
} | null> {
  try {
    const response = await fetchServerApi("/system/readiness")
    if (!response.ok) {
      return null
    }
    return (await response.json()) as {
      status: string
      blocking_warnings: string[]
      ready_for_distributed_workers: boolean
    }
  } catch {
    return null
  }
}

export async function getServerSystemExecutionConfig(): Promise<SystemExecutionConfigPayload | null> {
  try {
    const response = await fetchServerApi("/system/config")
    if (!response.ok) {
      return null
    }
    return (await response.json()) as SystemExecutionConfigPayload
  } catch {
    return null
  }
}

export async function getServerPersonalExecutionConfig(): Promise<PersonalExecutionConfigPayload | null> {
  try {
    const response = await fetchServerApi("/personal/config")
    if (!response.ok) {
      return null
    }
    return (await response.json()) as PersonalExecutionConfigPayload
  } catch {
    return null
  }
}

export async function getServerTitleContext(): Promise<TitleContextPayload | null> {
  try {
    const response = await fetchServerApi("/title/context")
    if (!response.ok) {
      return {
        ready: false,
        default_model: "",
        default_template_key: "default",
        image_template_key: "image_analysis",
        template_options: [],
        provider: "",
        config_source: "unavailable",
        warnings: ["标题执行上下文获取失败，请刷新页面或检查服务状态。"],
        blocking_reason: "标题执行上下文获取失败，请刷新页面或检查服务状态。",
        current_project: null,
        current_team: null,
      }
    }
    return (await response.json()) as TitleContextPayload
  } catch {
    return {
      ready: false,
      default_model: "",
      default_template_key: "default",
      image_template_key: "image_analysis",
      template_options: [],
      provider: "",
      config_source: "unavailable",
      warnings: ["标题执行上下文获取失败，请刷新页面或检查服务状态。"],
      blocking_reason: "标题执行上下文获取失败，请刷新页面或检查服务状态。",
      current_project: null,
      current_team: null,
    }
  }
}
