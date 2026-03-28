import type { NextAuthConfig } from "next-auth"
import Credentials from "next-auth/providers/credentials"

const casdoorEnabled = Boolean(
  process.env.CASDOOR_ISSUER &&
    process.env.CASDOOR_CLIENT_ID &&
    process.env.CASDOOR_CLIENT_SECRET,
)

const bootstrapEmail = (process.env.BOOTSTRAP_LOGIN_EMAIL || "").trim().toLowerCase()
const bootstrapPassword = process.env.BOOTSTRAP_LOGIN_PASSWORD || ""
const bootstrapName = (process.env.BOOTSTRAP_LOGIN_NAME || "").trim() || "Platform Admin"

const providers: NonNullable<NextAuthConfig["providers"]> = []

if (casdoorEnabled) {
  providers.push({
    id: "casdoor",
    name: "Casdoor",
    type: "oidc",
    issuer: process.env.CASDOOR_ISSUER,
    clientId: process.env.CASDOOR_CLIENT_ID,
    clientSecret: process.env.CASDOOR_CLIENT_SECRET,
    checks: ["pkce", "state"],
    authorization: {
      params: {
        scope: "openid profile email",
      },
    },
    profile(profile) {
      return {
        id: String(profile.sub || profile.id || ""),
        name: String(profile.name || profile.preferred_username || ""),
        email: typeof profile.email === "string" ? profile.email : null,
        image: typeof profile.picture === "string" ? profile.picture : null,
      }
    },
  })
}

if (bootstrapEmail && bootstrapPassword) {
  providers.push(
    Credentials({
      id: "bootstrap",
      name: "内置引导账号",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      authorize(credentials) {
        const email =
          typeof credentials?.email === "string"
            ? credentials.email.trim().toLowerCase()
            : ""
        const password =
          typeof credentials?.password === "string" ? credentials.password : ""

        if (email !== bootstrapEmail || password !== bootstrapPassword) {
          return null
        }

        return {
          id: `bootstrap:${bootstrapEmail}`,
          name: bootstrapName,
          email: bootstrapEmail,
        }
      },
    }),
  )
}

const authConfig: NextAuthConfig = {
  providers,
  trustHost: true,
}

export default authConfig
