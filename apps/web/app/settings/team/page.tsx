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
      <TeamSettingsPanel session={session} isAdmin={access.isAdmin} />
    </AppShell>
  )
}
