import { auth } from "../../../auth"
import { requireTeamMember } from "../../../lib/guards"
import { AppShell } from "../../../components/app-shell"
import { TeamSettingsPanel } from "../../../components/team-settings-panel"
import { getSessionAccess } from "../../../lib/access"

export default async function TeamSettingsPage() {
  await requireTeamMember()
  const session = await auth()
  const access = getSessionAccess(session)

  return (
    <AppShell title="团队/管理员" subtitle="Team Settings">
      <TeamSettingsPanel
        apiBaseUrl={process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}
        session={session}
        isAdmin={access.isAdmin}
      />
    </AppShell>
  )
}
