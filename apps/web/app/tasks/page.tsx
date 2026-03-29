import { requireSignedIn } from "../../lib/guards"
import { AppShell } from "../../components/app-shell"
import { TasksWorkspace } from "../../components/tasks-workspace"

export default async function TasksPage() {
  await requireSignedIn()

  return (
    <AppShell title="任务中心" subtitle="Task Center">
      <TasksWorkspace apiBaseUrl="/api/platform" />
    </AppShell>
  )
}
