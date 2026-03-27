import NextAuth, { type NextAuthConfig } from "next-auth"

const authConfig: NextAuthConfig = {
  providers: [
    {
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
    },
  ],
  trustHost: true,
}

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig)
