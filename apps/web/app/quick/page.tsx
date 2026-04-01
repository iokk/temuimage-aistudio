import { requireSignedIn } from "../../lib/guards"
import { AppShell } from "../../components/app-shell"
import { QuickWorkspace } from "../../components/quick-workspace"
import { getServerRuntimePayload } from "../../lib/server-api"

export default async function QuickPage() {
  await requireSignedIn()
  const runtime = await getServerRuntimePayload()

  return (
    <AppShell title="快速出图" subtitle="Quick Generation">
      <QuickWorkspace
        apiBaseUrl="/api/platform"
        currentProject={runtime?.current_project || null}
      />
    </AppShell>
  )
}
