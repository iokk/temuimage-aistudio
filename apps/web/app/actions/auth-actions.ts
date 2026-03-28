"use server"

import { signIn, signOut } from "../../auth"

export async function signInWithCasdoor(formData: FormData) {
  const mode = formData.get("mode") === "personal" ? "personal" : "team"
  const redirectTo =
    mode === "personal" ? "/settings/personal" : "/settings/team"

  await signIn("casdoor", { redirectTo })
}

export async function signOutCurrentUser() {
  await signOut({ redirectTo: "/login" })
}
