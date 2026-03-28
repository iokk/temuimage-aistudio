import NextAuth from "next-auth"
import { NextResponse } from "next/server"

import authConfig from "./auth.config"
import { getEmailAccess } from "./lib/access"

const { auth } = NextAuth(authConfig)

const signedInRoutes = ["/tasks", "/settings/personal", "/settings/team", "/admin"]

export default auth((request) => {
  const { nextUrl } = request
  const isSignedInRoute = signedInRoutes.some(
    (route) => nextUrl.pathname === route || nextUrl.pathname.startsWith(`${route}/`),
  )

  if (!request.auth && isSignedInRoute) {
    return NextResponse.redirect(new URL("/login", nextUrl))
  }

  if (!request.auth) {
    return NextResponse.next()
  }

  const access = getEmailAccess(request.auth.user?.email)

  if (nextUrl.pathname === "/admin" || nextUrl.pathname.startsWith("/admin/")) {
    if (!access.isAdmin) {
      return NextResponse.redirect(new URL("/settings/team", nextUrl))
    }
  }

  if (nextUrl.pathname === "/settings/team" || nextUrl.pathname.startsWith("/settings/team/")) {
    if (!access.isTeamMember) {
      return NextResponse.redirect(new URL("/settings/personal", nextUrl))
    }
  }

  return NextResponse.next()
})

export const config = {
  matcher: ["/tasks/:path*", "/settings/:path*", "/admin/:path*"],
}
