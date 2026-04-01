import { getServerReadinessPayload, getServerRuntimePayload } from "./server-api"

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
  default_translate_provider: string
  default_translate_image_model: string
  default_translate_analysis_model: string
  default_quick_image_model: string
  default_batch_image_model: string
  relay_api_base_configured: boolean
  relay_api_key_configured: boolean
  gemini_api_key_configured: boolean
  system_config_source: string
  system_config_persistence_enabled: boolean
  warnings: string[]
  ready_for_distributed_workers: boolean
  current_user: {
    id: string
    email: string
    name: string
    mode: string
    issuer: string
    subject: string
    email_verified: boolean
    last_login_at: string | null
    is_admin: boolean
    is_team_member: boolean
  } | null
  current_team: {
    organization_id: string
    organization_name: string
    organization_slug: string
    membership_role: string
  } | null
  current_project: {
    project_id: string
    project_name: string
    project_slug: string
    project_status: string
  } | null
}

type SystemExecutionConfigPayload = {
  title_model: string
  translate_provider: string
  translate_image_model: string
  translate_analysis_model: string
  quick_image_model: string
  batch_image_model: string
  relay_api_base: string
  relay_api_key_preview: string
  relay_default_image_model: string
  gemini_api_key_preview: string
  source: string
  persistence_enabled: boolean
}

type PersonalExecutionConfigPayload = {
  use_personal_credentials: boolean
  provider: string
  relay_api_base: string
  relay_api_key_preview: string
  relay_default_image_model: string
  gemini_api_key_preview: string
  source: string
  persistence_enabled: boolean
}

type TitleContextPayload = {
  ready: boolean
  default_model: string
  default_template_key: string
  image_template_key: string
  template_options: Array<{
    key: string
    name: string
    desc: string
  }>
  provider: string
  config_source: string
  warnings: string[]
  blocking_reason: string | null
  current_project: RuntimePayload["current_project"] | null
  current_team: RuntimePayload["current_team"] | null
}

export async function getRuntimePayload(): Promise<RuntimePayload | null> {
  return getServerRuntimePayload()
}

export async function getReadinessPayload(): Promise<{
  status: string
  blocking_warnings: string[]
  ready_for_distributed_workers: boolean
} | null> {
  return getServerReadinessPayload()
}

export type {
  PersonalExecutionConfigPayload,
  RuntimePayload,
  SystemExecutionConfigPayload,
  TitleContextPayload,
}
