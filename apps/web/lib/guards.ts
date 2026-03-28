import { redirect } from "next/navigation"

import { auth } from "../auth"
import { getSessionAccess } from "./access"

export async function requireSignedIn() {
  const session = await auth()

  if (!session) {
    redirect("/login")
  }

  return session
}

export async function requireTeamMember() {
  const session = await requireSignedIn()
  const access = getSessionAccess(session)

  if (!access.isTeamMember) {
    redirect("/settings/personal")
  }

  return session
}

export async function requireAdmin() {
  const session = await requireSignedIn()
  const access = getSessionAccess(session)

  if (!access.isAdmin) {
    redirect("/settings/team")
  }

  return session
}
