import Link from "next/link"

import { AppShell } from "../components/app-shell"

const features = [
  { href: "/batch", title: "批量出图", desc: "多张参考图、多类型卖点图的标准流程" },
  { href: "/quick", title: "快速出图", desc: "更少步骤，适合单批快速生成" },
  { href: "/title", title: "标题优化", desc: "结合图片与补充信息输出标题" },
  { href: "/translate", title: "图片翻译", desc: "提取文字、翻译并生成译后图片" },
]

export default function HomePage() {
  return (
    <AppShell
      title="小白图"
      subtitle="跨境电商出图系统 · AI Studio"
    >
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
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
      </section>
    </AppShell>
  )
}
