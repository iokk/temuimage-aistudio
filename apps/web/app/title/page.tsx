import { requireSignedIn } from "../../lib/guards"
import { AppShell } from "../../components/app-shell"
import { TitleWorkspace } from "../../components/title-workspace"

export default async function TitlePage() {
  await requireSignedIn()

  return (
    <AppShell title="标题优化" subtitle="Title Optimization">
      <TitleWorkspace apiBaseUrl="/api/platform" />
    </AppShell>
  )
}
