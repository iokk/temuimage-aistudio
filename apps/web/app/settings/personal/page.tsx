import { auth } from "../../../auth"
import { AppShell } from "../../../components/app-shell"
import { PersonalSettingsPanel } from "../../../components/personal-settings-panel"
import { requireSignedIn } from "../../../lib/guards"

export default async function PersonalSettingsPage() {
  await requireSignedIn()
  const session = await auth()

  return (
    <AppShell title="个人模式" subtitle="Personal Settings">
      <PersonalSettingsPanel session={session} />
    </AppShell>
  )
}
