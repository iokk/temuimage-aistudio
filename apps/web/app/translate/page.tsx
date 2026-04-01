import { requireSignedIn } from "../../lib/guards"
import { AppShell } from "../../components/app-shell"
import { TranslateWorkspace } from "../../components/translate-workspace"
import { getServerRuntimePayload } from "../../lib/server-api"

export default async function TranslatePage() {
  await requireSignedIn()
  const runtime = await getServerRuntimePayload()

  return (
    <AppShell title="图片翻译" subtitle="Image Translation">
      <TranslateWorkspace
        apiBaseUrl="/api/platform"
        currentProject={runtime?.current_project || null}
      />
    </AppShell>
  )
}
