import Link from "next/link"

import type { Session } from "next-auth"

import { getRuntimePayload } from "../lib/runtime"
import { getServerPersonalExecutionConfig } from "../lib/server-api"
import { PersonalConfigPanel } from "./personal-config-panel"

export async function PersonalSettingsPanel({
  session,
}: {
  session: Session | null
}) {
  const runtime = await getRuntimePayload()
  const personalConfig = await getServerPersonalExecutionConfig()

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
        <PersonalConfigPanel
          apiBaseUrl="/api/platform"
          currentProject={runtime?.current_project || null}
          initialConfig={personalConfig}
        />

        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h3 className="text-xl font-bold text-slate-950">持久化账号状态</h3>
          <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
            <p>账号 ID：{runtime?.current_user?.id || "当前未写入持久化账号"}</p>
            <p>签发方：{runtime?.current_user?.issuer || "未记录"}</p>
            <p>主体标识：{runtime?.current_user?.subject || "未记录"}</p>
            <p>邮箱校验：{runtime?.current_user?.email_verified ? "已验证" : "未验证"}</p>
            <p>
              最近登录：
              {runtime?.current_user?.last_login_at
                ? new Date(runtime.current_user.last_login_at).toLocaleString("zh-CN")
                : "尚未记录"}
            </p>
            <p>
              当前权限：
              {runtime?.current_user?.is_admin
                ? "管理员 + 团队成员"
                : runtime?.current_user?.is_team_member
                  ? "团队成员"
                  : "个人模式"}
            </p>
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
