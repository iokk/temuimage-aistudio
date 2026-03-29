import { requireAdmin } from "../../lib/guards"
import { AppShell } from "../../components/app-shell"
import { AdminRuntimePanel } from "../../components/admin-runtime-panel"

export default async function AdminPage() {
  await requireAdmin()

  return (
    <AppShell title="管理后台" subtitle="Admin Panel">
      <AdminRuntimePanel />
    </AppShell>
  )
}
