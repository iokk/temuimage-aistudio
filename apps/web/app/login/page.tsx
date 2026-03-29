import Link from "next/link"

import { auth } from "../../auth"
import { signInWithCasdoor, signOutCurrentUser } from "../actions/auth-actions"
import { AppShell } from "../../components/app-shell"

const modeCards = [
  {
    mode: "personal",
    title: "个人模式",
    description: "登录后进入个人凭据区，配置自己的 Gemini Key 或个人中转站。",
  },
  {
    mode: "team",
    title: "团队模式",
    description: "登录后进入团队配置区，使用官方账号和管理员统一系统配置。",
  },
] as const

export default async function LoginPage() {
  const session = await auth()
  const casdoorEnabled = Boolean(
    process.env.CASDOOR_ISSUER &&
      process.env.CASDOOR_CLIENT_ID &&
      process.env.CASDOOR_CLIENT_SECRET,
  )

  return (
    <AppShell title="登录" subtitle="Casdoor Unified Identity">
      {session ? (
        <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
            <h3 className="text-2xl font-bold text-slate-950">已完成统一登录</h3>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              当前账号已接入系统。接下来可根据使用场景进入个人模式或团队模式继续配置。
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <Link
                href="/settings/personal"
                className="rounded-2xl border border-slate-200 px-5 py-4 text-sm font-medium text-slate-800 transition hover:border-sky-300 hover:bg-sky-50"
              >
                进入个人模式
              </Link>
              <Link
                href="/settings/team"
                className="rounded-2xl border border-slate-200 px-5 py-4 text-sm font-medium text-slate-800 transition hover:border-sky-300 hover:bg-sky-50"
              >
                进入团队模式
              </Link>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
            <p className="text-sm font-semibold text-slate-900">
              {session.user?.name || "平台用户"}
            </p>
            <p className="mt-2 text-sm text-slate-500">
              {session.user?.email || "当前账号尚未返回邮箱信息。"}
            </p>
            <form action={signOutCurrentUser} className="mt-6">
              <button
                type="submit"
                className="w-full rounded-2xl bg-slate-900 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-700"
              >
                退出登录
              </button>
            </form>
          </div>
        </section>
      ) : (
        <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
            <h3 className="text-2xl font-bold text-slate-950">统一登录入口</h3>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              个人模式与团队模式共用 Casdoor 单点登录。登录后会根据模式进入个人配置区或团队配置区。
            </p>
            <div className="mt-6 grid gap-4">
              {casdoorEnabled ? (
                <div className="rounded-2xl border border-slate-200 p-5">
                  <h4 className="text-lg font-semibold text-slate-950">Casdoor 单点登录</h4>
                  <p className="mt-2 text-sm leading-7 text-slate-600">
                    若你已经配置 Casdoor，可继续使用统一 OIDC 登录接入个人模式和团队模式。
                  </p>
                  <div className="mt-4 grid gap-4 sm:grid-cols-2">
                    {modeCards.map((item) => (
                      <form
                        key={`casdoor-${item.mode}`}
                        action={signInWithCasdoor}
                        className="rounded-2xl border border-slate-200 p-5"
                      >
                        <input type="hidden" name="mode" value={item.mode} />
                        <h5 className="text-base font-semibold text-slate-950">{item.title}</h5>
                        <p className="mt-2 text-sm leading-7 text-slate-600">
                          {item.description}
                        </p>
                        <button
                          type="submit"
                          className="mt-4 rounded-xl bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-500"
                        >
                          使用 Casdoor 登录
                        </button>
                      </form>
                    ))}
                  </div>
                </div>
              ) : null}

              {!casdoorEnabled ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm leading-7 text-amber-900">
                  当前尚未配置 Casdoor。请先设置 `CASDOOR_ISSUER`、`CASDOOR_CLIENT_ID`
                  和 `CASDOOR_CLIENT_SECRET`，再启用正式登录入口。
                </div>
              ) : null}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
            <h3 className="text-xl font-bold text-slate-950">本阶段已接通</h3>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
              <p>Auth.js 已正式收口到 Casdoor OIDC 单入口。</p>
              <p>登录后会根据模式跳转到个人配置或团队配置页面。</p>
              <p>后续 API、任务 owner 和团队权限会继续沿着 Casdoor 身份贯通。</p>
            </div>
          </div>
        </section>
      )}
    </AppShell>
  )
}
