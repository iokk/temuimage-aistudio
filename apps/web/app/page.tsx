import Link from "next/link"

import { auth } from "../auth"
import { AppShell } from "../components/app-shell"

const features = [
  { href: "/batch", title: "批量出图", desc: "多张参考图、多类型卖点图的标准流程" },
  { href: "/quick", title: "快速出图", desc: "更少步骤，适合单批快速生成" },
  { href: "/title", title: "标题优化", desc: "结合图片与补充信息输出标题" },
  { href: "/translate", title: "图片翻译", desc: "提取文字、翻译并生成译后图片" },
]

export default async function HomePage() {
  const session = await auth()

  return (
    <AppShell
      title="小白图"
      subtitle="跨境电商出图系统 · AI Studio"
    >
      <section className="grid gap-6">
        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h3 className="text-2xl font-bold text-slate-950">
            {session ? `欢迎回来，${session.user?.name || "团队成员"}` : "先完成统一登录，再进入工作流"}
          </h3>
          <p className="mt-3 text-sm leading-7 text-slate-600">
            {session
              ? "当前系统已接通统一登录、任务中心和四个核心能力页，可直接进入部署联调。"
              : "新系统不再提供访客模式。登录后可根据个人模式或团队模式进入对应配置区，再开始批量出图、快速出图、标题优化和图片翻译。"}
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href={session ? "/tasks" : "/login"}
              className="rounded-2xl bg-sky-600 px-5 py-3 text-sm font-medium text-white transition hover:bg-sky-500"
            >
              {session ? "查看任务中心" : "前往登录"}
            </Link>
            <Link
              href="/settings/personal"
              className="rounded-2xl border border-slate-200 px-5 py-3 text-sm font-medium text-slate-800 transition hover:border-sky-300 hover:bg-sky-50"
            >
              个人模式配置
            </Link>
            <Link
              href="/settings/team"
              className="rounded-2xl border border-slate-200 px-5 py-3 text-sm font-medium text-slate-800 transition hover:border-sky-300 hover:bg-sky-50"
            >
              团队模式配置
            </Link>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {features.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-sky-300 hover:bg-sky-50"
            >
              <h2 className="text-lg font-semibold text-slate-900">{item.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">{item.desc}</p>
            </Link>
          ))}
        </div>
      </section>
    </AppShell>
  )
}
