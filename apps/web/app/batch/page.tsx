import { requireSignedIn } from "../../lib/guards"
import { AppShell } from "../../components/app-shell"
import { BatchWorkspace } from "../../components/batch-workspace"

export default async function BatchPage() {
  await requireSignedIn()

  return (
    <AppShell title="批量出图" subtitle="Batch Generation">
      <BatchWorkspace
        apiBaseUrl={process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}
      />
    </AppShell>
  )
}
