type RuntimePayload = {
  app_name: string
  app_version: string
  database_configured: boolean
  redis_configured: boolean
  auth_provider: string
  active_backend: string
  preferred_backend: string
  fallback_reason: string
  persistence_ready: boolean
  active_execution_backend: string
  preferred_execution_backend: string
  execution_fallback_reason: string
  execution_queue_ready: boolean
  execution_storage_compatible: boolean
  team_admin_count: number
  team_allowed_domain_count: number
  default_title_model: string
  default_translate_image_model: string
  default_translate_analysis_model: string
  default_quick_image_model: string
  default_batch_image_model: string
  warnings: string[]
  ready_for_distributed_workers: boolean
}

export async function getRuntimePayload(apiBaseUrl: string): Promise<RuntimePayload | null> {
  try {
    const response = await fetch(`${apiBaseUrl.replace(/\/$/, "")}/v1/system/runtime`, {
      cache: "no-store",
    })
    if (!response.ok) {
      return null
    }
    return (await response.json()) as RuntimePayload
  } catch {
    return null
  }
}

export async function getReadinessPayload(apiBaseUrl: string): Promise<{
  status: string
  blocking_warnings: string[]
  ready_for_distributed_workers: boolean
} | null> {
  try {
    const response = await fetch(`${apiBaseUrl.replace(/\/$/, "")}/v1/system/readiness`, {
      cache: "no-store",
    })
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

export type { RuntimePayload }
