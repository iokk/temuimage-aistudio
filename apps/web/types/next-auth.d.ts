import type { DefaultSession } from "next-auth"

declare module "next-auth" {
  interface Session {
    accessToken?: string
    idToken?: string
    issuer?: string
    subject?: string
    user?: DefaultSession["user"] & {
      id: string
      casdoorEmailVerified?: boolean
    }
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken?: string
    idToken?: string
    issuer?: string
    subject?: string
    casdoorEmailVerified?: boolean
  }
}
