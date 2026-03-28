import Link from "next/link"

import { auth } from "../auth"
import { signOutCurrentUser } from "../app/actions/auth-actions"

const navItems = [
  { href: "/batch", label: "批量出图" },
  { href: "/quick", label: "快速出图" },
  { href: "/title", label: "标题优化" },
  { href: "/translate", label: "图片翻译" },
]

export async function AppShell({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle: string
  children: React.ReactNode
}) {
  const session = await auth()
  const today = new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date())

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <div className="mx-auto flex min-h-screen max-w-[1600px]">
        <aside className="hidden w-72 shrink-0 border-r border-slate-200 bg-white xl:block">
          <div className="sticky top-0 p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-700">
              AI Studio
            </p>
            <h1 className="mt-3 text-2xl font-black tracking-tight">小白图</h1>
            <p className="mt-1 text-sm text-slate-500">跨境电商出图系统</p>

            <nav className="mt-8 space-y-2">
              <Link href="/" className="block rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 hover:border-sky-300 hover:bg-sky-50">
                首页
              </Link>
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="block rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 hover:border-sky-300 hover:bg-sky-50"
                >
                  {item.label}
                </Link>
              ))}
            </nav>

            <div className="mt-8 space-y-2 text-sm text-slate-500">
              <Link href="/tasks" className="block rounded-xl border border-slate-200 px-4 py-3 hover:border-slate-300 hover:bg-slate-50">
                任务中心
              </Link>
              <Link href="/settings/personal" className="block rounded-xl border border-slate-200 px-4 py-3 hover:border-slate-300 hover:bg-slate-50">
                个人模式
              </Link>
              <Link href="/settings/team" className="block rounded-xl border border-slate-200 px-4 py-3 hover:border-slate-300 hover:bg-slate-50">
                团队/管理员
              </Link>
              <Link href="/admin" className="block rounded-xl border border-slate-200 px-4 py-3 hover:border-slate-300 hover:bg-slate-50">
                管理后台
              </Link>
            </div>

            <div className="mt-8 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              <p className="font-semibold text-slate-900">
                {session?.user?.name || "未登录"}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {session?.user?.email || "请先完成登录后再进入个人或团队配置。"}
              </p>
              {session ? (
                <form action={signOutCurrentUser} className="mt-4">
                  <button
                    type="submit"
                    className="w-full rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700"
                  >
                    退出登录
                  </button>
                </form>
              ) : (
                <Link
                  href="/login"
                  className="mt-4 block rounded-xl bg-sky-600 px-4 py-2 text-center text-sm font-medium text-white transition hover:bg-sky-500"
                >
                  去登录
                </Link>
              )}
            </div>
          </div>
        </aside>

        <main className="flex-1 px-6 py-8 lg:px-10">
          <div className="mb-6 grid gap-2 xl:hidden sm:grid-cols-2">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:bg-sky-50"
              >
                {item.label}
              </Link>
            ))}
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-700">
              {subtitle}
            </p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-950">
              {title}
            </h2>
          </div>

          <div className="mt-6">{children}</div>

          <footer className="mt-8 rounded-3xl border border-slate-200 bg-white px-6 py-4 text-sm text-slate-500 shadow-sm">
            深圳祖尔科技有限公司 · {today} · v0.1.0
          </footer>
        </main>
      </div>
    </div>
  )
}
