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

  return (
    <AppShell title="登录" subtitle="Casdoor Authentication">
      {session ? (
        <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
            <h3 className="text-2xl font-bold text-slate-950">已完成统一登录</h3>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              当前账号已接入 Casdoor。接下来可根据使用场景进入个人模式或团队模式继续配置。
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
              {session.user?.name || "Casdoor 用户"}
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
              个人模式与团队模式共用 Casdoor 登录。区别只在登录后的落点和配置范围，避免访客模式带来的权限和配置混乱。
            </p>
            <div className="mt-6 grid gap-4">
              {modeCards.map((item) => (
                <form
                  key={item.mode}
                  action={signInWithCasdoor}
                  className="rounded-2xl border border-slate-200 p-5"
                >
                  <input type="hidden" name="mode" value={item.mode} />
                  <h4 className="text-lg font-semibold text-slate-950">{item.title}</h4>
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

          <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
            <h3 className="text-xl font-bold text-slate-950">本阶段已接通</h3>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
              <p>Auth.js 已连接 Casdoor OIDC provider。</p>
              <p>登录后会根据模式跳转到个人配置或团队配置页面。</p>
              <p>后续会继续补齐组织关系、角色权限和管理员工作台。</p>
            </div>
          </div>
        </section>
      )}
    </AppShell>
  )
}
