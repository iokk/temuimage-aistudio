import type { NextAuthConfig } from "next-auth"

const casdoorEnabled = Boolean(
  process.env.CASDOOR_ISSUER &&
    process.env.CASDOOR_CLIENT_ID &&
    process.env.CASDOOR_CLIENT_SECRET,
)

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

const authConfig: NextAuthConfig = {
  providers,
  trustHost: true,
  callbacks: {
    jwt({ token, account, profile }) {
      if (account?.access_token) {
        token.accessToken = account.access_token
      }

      if (account?.id_token) {
        token.idToken = account.id_token
      }

      if (typeof token.sub === "string") {
        token.subject = token.sub
      }

      if (process.env.CASDOOR_ISSUER) {
        token.issuer = process.env.CASDOOR_ISSUER
      }

      const emailVerified = profile?.email_verified
      if (typeof emailVerified === "boolean") {
        token.casdoorEmailVerified = emailVerified
      }

      return token
    },
    session({ session, token }) {
      if (session.user) {
        session.user.id = typeof token.sub === "string" ? token.sub : ""
        session.user.casdoorEmailVerified = Boolean(token.casdoorEmailVerified)
      }

      session.accessToken =
        typeof token.accessToken === "string" ? token.accessToken : undefined
      session.idToken = typeof token.idToken === "string" ? token.idToken : undefined
      session.subject =
        typeof token.subject === "string"
          ? token.subject
          : typeof token.sub === "string"
            ? token.sub
            : undefined
      session.issuer =
        typeof token.issuer === "string" ? token.issuer : process.env.CASDOOR_ISSUER

      return session
    },
  },
}

export default authConfig
