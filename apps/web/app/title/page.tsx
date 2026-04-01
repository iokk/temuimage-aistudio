import { requireSignedIn } from "../../lib/guards"
import { AppShell } from "../../components/app-shell"
import { TitleWorkspace } from "../../components/title-workspace"
import { getServerRuntimePayload, getServerTitleContext } from "../../lib/server-api"

export default async function TitlePage() {
  await requireSignedIn()
  const runtime = await getServerRuntimePayload()
  const titleContext = await getServerTitleContext()

  return (
    <AppShell title="标题优化" subtitle="Title Optimization">
      <TitleWorkspace
        apiBaseUrl="/api/platform"
        currentProject={runtime?.current_project || null}
        titleContext={titleContext}
      />
    </AppShell>
  )
}
