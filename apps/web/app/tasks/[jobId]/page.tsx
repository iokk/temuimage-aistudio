import { notFound } from "next/navigation"

import { AppShell } from "../../../components/app-shell"
import { TaskDetailView } from "../../../components/task-detail-view"
import { requireSignedIn } from "../../../lib/guards"
import { getJob } from "../../../lib/job-client"

export default async function TaskDetailPage({
  params,
}: {
  params: Promise<{ jobId: string }>
}) {
  await requireSignedIn()
  const { jobId } = await params
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

  try {
    const payload = await getJob(apiBaseUrl, jobId)
    return (
      <AppShell title={payload.job.title} subtitle="Task Detail">
        <TaskDetailView apiBaseUrl={apiBaseUrl} initialJob={payload.job} />
      </AppShell>
    )
  } catch {
    notFound()
  }
}
