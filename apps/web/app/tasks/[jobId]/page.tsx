import { notFound } from "next/navigation"

import { AppShell } from "../../../components/app-shell"
import { TaskDetailView } from "../../../components/task-detail-view"
import { requireSignedIn } from "../../../lib/guards"
import { getServerJob } from "../../../lib/server-api"

export default async function TaskDetailPage({
  params,
}: {
  params: Promise<{ jobId: string }>
}) {
  await requireSignedIn()
  const { jobId } = await params

  try {
    const payload = await getServerJob(jobId)
    return (
      <AppShell title={payload.job.title} subtitle="任务详情">
        <TaskDetailView apiBaseUrl="/api/platform" initialJob={payload.job} />
      </AppShell>
    )
  } catch {
    notFound()
  }
}
