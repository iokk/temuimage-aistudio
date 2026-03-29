import Link from "next/link"

import type { Session } from "next-auth"

import { getRuntimePayload } from "../lib/runtime"

export async function PersonalSettingsPanel({
  session,
}: {
  session: Session | null
}) {
  const runtime = await getRuntimePayload()

  return (
    <section className="grid gap-6">
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-500">当前账号</p>
          <p className="mt-2 text-xl font-bold text-slate-950">
            {session?.user?.name || "Casdoor 用户"}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            {session?.user?.email || "当前未返回邮箱信息"}
          </p>
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-500">认证方式</p>
          <p className="mt-2 text-xl font-bold text-slate-950">
            {runtime?.auth_provider || "Casdoor"}
          </p>
          <p className="mt-2 text-sm text-slate-500">个人模式不再提供访客入口</p>
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-500">默认标题模型</p>
          <p className="mt-2 text-xl font-bold text-slate-950">
            {runtime?.default_title_model || "gemini-3.1-pro"}
          </p>
          <p className="mt-2 text-sm text-slate-500">用于标题优化和出图联动标题</p>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h3 className="text-xl font-bold text-slate-950">个人模式说明</h3>
          <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
            <p>个人模式面向单人使用，后续这里会接个人 Gemini Key 或个人中转站配置。</p>
            <p>当前新栈已经可以先体验标题优化、图片翻译、快速出图、批量出图和任务中心。</p>
            <p>模型默认方向已经固定：标题优先走 `gemini-3.1-pro`。</p>
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h3 className="text-xl font-bold text-slate-950">当前运行状态</h3>
          <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
            <p>任务存储：{runtime?.active_backend || "memory"}</p>
            <p>异步执行：{runtime?.active_execution_backend || "inline"}</p>
            <p>分布式 worker 就绪：{runtime?.ready_for_distributed_workers ? "已满足" : "未满足"}</p>
            <p>图片翻译图像模型：{runtime?.default_translate_image_model || "gemini-3.1-flash-image-preview"}</p>
            <p>图片翻译分析模型：{runtime?.default_translate_analysis_model || "gemini-3.1-pro"}</p>
          </div>
        </div>
      </div>

      {runtime?.warnings?.length ? (
        <div className="rounded-3xl border border-amber-200 bg-amber-50 p-8 shadow-sm">
          <h3 className="text-xl font-bold text-amber-900">当前警告</h3>
          <div className="mt-4 space-y-2 text-sm leading-7 text-amber-800">
            {runtime.warnings.map((warning, index) => (
              <p key={`${warning}-${index}`}>- {warning}</p>
            ))}
          </div>
        </div>
      ) : null}

      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <h3 className="text-xl font-bold text-slate-950">快捷入口</h3>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link href="/title" className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50">
            打开标题优化
          </Link>
          <Link href="/translate" className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50">
            打开图片翻译
          </Link>
          <Link href="/tasks" className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50">
            查看任务中心
          </Link>
        </div>
      </div>
    </section>
  )
}
