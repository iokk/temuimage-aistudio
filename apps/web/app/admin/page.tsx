import { requireAdmin } from "../../lib/guards"
import { AppShell } from "../../components/app-shell"
import { AdminRuntimePanel } from "../../components/admin-runtime-panel"

export default async function AdminPage() {
  await requireAdmin()

  return (
    <AppShell title="管理后台" subtitle="Admin Panel">
      <AdminRuntimePanel
        apiBaseUrl={process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}
      />
    </AppShell>
  )
}
