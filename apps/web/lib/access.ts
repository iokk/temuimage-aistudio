import type { Session } from "next-auth"

function parseCsv(value: string | undefined) {
  return (value || "")
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
}

export function getEmailAccess(email: string | null | undefined) {
  const normalizedEmail = (email || "").trim().toLowerCase()
  const adminEmails = parseCsv(process.env.TEAM_ADMIN_EMAILS)
  const allowedDomains = parseCsv(process.env.TEAM_ALLOWED_EMAIL_DOMAINS)
  const emailDomain = normalizedEmail.includes("@")
    ? normalizedEmail.split("@").pop() || ""
    : ""

  const isAdmin = Boolean(normalizedEmail) && adminEmails.includes(normalizedEmail)
  const isTeamMember =
    isAdmin ||
    (Boolean(emailDomain) && allowedDomains.includes(emailDomain))

  return {
    isAdmin,
    isTeamMember,
  }
}

export function getSessionAccess(session: Session | null) {
  return getEmailAccess(session?.user?.email)
}
