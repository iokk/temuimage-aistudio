export type JobRecord = {
  id: string
  task_type: string
  status: string
  summary: string
  page: string
  title: string
  icon: string
  payload: Record<string, unknown>
  result: Record<string, unknown>
  created_at: string
  updated_at: string
  history: Array<{
    status: string
    at: string
    message: string
  }>
}

type JobResponse = {
  job: JobRecord
  pending_count: number
  execution_backend?: string
}

function buildJobApiUrl(apiBaseUrl: string, path: string) {
  const normalizedBaseUrl = apiBaseUrl.replace(/\/$/, "")

  if (normalizedBaseUrl.endsWith("/api/platform")) {
    return `${normalizedBaseUrl}${path}`
  }

  return `${normalizedBaseUrl}/v1${path}`
}

export async function createJob(apiBaseUrl: string, input: {
  task_type: string
  summary: string
  status?: string
  payload?: Record<string, unknown>
  result?: Record<string, unknown>
}) {
  const response = await fetch(buildJobApiUrl(apiBaseUrl, "/jobs/submit"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      task_type: input.task_type,
      summary: input.summary,
      status: input.status || "completed",
      payload: input.payload || {},
      result: input.result || {},
    }),
  })

  if (!response.ok) {
    throw new Error("任务中心暂时不可用，请稍后重试。")
  }

  return (await response.json()) as JobResponse
}

export async function submitAsyncJob(apiBaseUrl: string, input: {
  task_type: string
  summary: string
  payload?: Record<string, unknown>
  result?: Record<string, unknown>
}) {
  const response = await fetch(buildJobApiUrl(apiBaseUrl, "/jobs/submit-async"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      task_type: input.task_type,
      summary: input.summary,
      payload: input.payload || {},
      result: input.result || {},
    }),
  })

  if (!response.ok) {
    throw new Error("任务提交失败，请稍后重试。")
  }

  return (await response.json()) as JobResponse
}

export async function updateJobStatus(
  apiBaseUrl: string,
  jobId: string,
  status: string,
  result?: Record<string, unknown>,
) {
  const response = await fetch(buildJobApiUrl(apiBaseUrl, `/jobs/${jobId}/status`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      status,
      result: result || {},
    }),
  })

  if (!response.ok) {
    throw new Error("任务状态更新失败，请稍后重试。")
  }

  return (await response.json()) as JobResponse
}

export async function getJob(apiBaseUrl: string, jobId: string) {
  const response = await fetch(buildJobApiUrl(apiBaseUrl, `/jobs/${jobId}`), {
    cache: "no-store",
  })

  if (!response.ok) {
    throw new Error("任务详情获取失败，请稍后重试。")
  }

  return (await response.json()) as { job: JobRecord }
}

export async function waitForJobCompletion(
  apiBaseUrl: string,
  jobId: string,
  options?: { intervalMs?: number; timeoutMs?: number },
) {
  const intervalMs = options?.intervalMs ?? 400
  const timeoutMs = options?.timeoutMs ?? 15000
  const startAt = Date.now()

  while (Date.now() - startAt < timeoutMs) {
    const payload = await getJob(apiBaseUrl, jobId)
    if (["completed", "failed"].includes(payload.job.status)) {
      return payload.job
    }
    await new Promise((resolve) => window.setTimeout(resolve, intervalMs))
  }

  throw new Error("任务执行超时，请稍后到任务中心查看。")
}
