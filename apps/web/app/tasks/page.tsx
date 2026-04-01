import { requireSignedIn } from "../../lib/guards"
import { AppShell } from "../../components/app-shell"
import { TasksWorkspace } from "../../components/tasks-workspace"
import { getServerRuntimePayload } from "../../lib/server-api"

export default async function TasksPage() {
  await requireSignedIn()
  const runtime = await getServerRuntimePayload()

  return (
    <AppShell title="任务中心" subtitle="Task Center">
      <TasksWorkspace
        apiBaseUrl="/api/platform"
        currentProject={runtime?.current_project || null}
      />
    </AppShell>
  )
}
