import { requireSignedIn } from "../../lib/guards"
import { AppShell } from "../../components/app-shell"
import { BatchWorkspace } from "../../components/batch-workspace"
import { getServerRuntimePayload } from "../../lib/server-api"

export default async function BatchPage() {
  await requireSignedIn()
  const runtime = await getServerRuntimePayload()

  return (
    <AppShell title="批量出图" subtitle="Batch Generation">
      <BatchWorkspace
        apiBaseUrl="/api/platform"
        currentProject={runtime?.current_project || null}
      />
    </AppShell>
  )
}
