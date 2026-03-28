import { requireSignedIn } from "../../lib/guards"
import { AppShell } from "../../components/app-shell"
import { TranslateWorkspace } from "../../components/translate-workspace"

export default async function TranslatePage() {
  await requireSignedIn()

  return (
    <AppShell title="图片翻译" subtitle="Image Translation">
      <TranslateWorkspace
        apiBaseUrl={process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}
      />
    </AppShell>
  )
}
