import { requireSignedIn } from "../../lib/guards"
import { AppShell } from "../../components/app-shell"
import { QuickWorkspace } from "../../components/quick-workspace"

export default async function QuickPage() {
  await requireSignedIn()

  return (
    <AppShell title="快速出图" subtitle="Quick Generation">
      <QuickWorkspace
        apiBaseUrl={process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}
      />
    </AppShell>
  )
}
