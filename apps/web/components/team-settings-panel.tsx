import Link from "next/link"

import type { Session } from "next-auth"

import { CurrentProjectPanel } from "./current-project-panel"
import { getRuntimePayload } from "../lib/runtime"

export async function TeamSettingsPanel({
  session,
  isAdmin,
}: {
  session: Session | null
  isAdmin: boolean
}) {
  const runtime = await getRuntimePayload()

  return (
    <section className="grid gap-6">
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-500">当前成员</p>
          <p className="mt-2 text-xl font-bold text-slate-950">
            {session?.user?.name || "团队成员"}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            {isAdmin ? "管理员权限" : "团队成员权限"}
          </p>
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-500">团队管理员配置</p>
          <p className="mt-2 text-xl font-bold text-slate-950">
            {runtime?.team_admin_count ?? 0}
          </p>
          <p className="mt-2 text-sm text-slate-500">环境变量中的管理员邮箱数量</p>
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-500">团队域名配置</p>
          <p className="mt-2 text-xl font-bold text-slate-950">
            {runtime?.team_allowed_domain_count ?? 0}
          </p>
          <p className="mt-2 text-sm text-slate-500">允许进入团队模式的邮箱域名数量</p>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h3 className="text-xl font-bold text-slate-950">当前团队状态</h3>
          <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
            <p>团队名称：{runtime?.current_team?.organization_name || "尚未创建默认团队"}</p>
            <p>团队标识：{runtime?.current_team?.organization_slug || "未记录"}</p>
            <p>成员角色：{runtime?.current_team?.membership_role || (isAdmin ? "admin" : "member")}</p>
            <p>持久化状态：{runtime?.current_team ? "已写入组织与成员关系" : "当前仍是仅环境权限"}</p>
            <p>默认项目管理：请在下方项目管理卡片中维护当前项目名称。</p>
            <p>标题默认模型：{runtime?.default_title_model || "gemini-3.1-pro"}</p>
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h3 className="text-xl font-bold text-slate-950">基础设施状态</h3>
          <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
            <p>任务存储：{runtime?.active_backend || "memory"}</p>
            <p>异步执行：{runtime?.active_execution_backend || "inline"}</p>
            <p>分布式 worker 就绪：{runtime?.ready_for_distributed_workers ? "已满足" : "未满足"}</p>
            <p>快速出图图像模型：{runtime?.default_quick_image_model || "gemini-3.1-flash-image-preview"}</p>
            <p>批量出图图像模型：{runtime?.default_batch_image_model || "gemini-3.1-flash-image-preview"}</p>
          </div>
        </div>
      </div>

      <CurrentProjectPanel
        initialProject={runtime?.current_project || null}
        isAdmin={isAdmin}
      />

      {runtime?.warnings?.length ? (
        <div className="rounded-3xl border border-amber-200 bg-amber-50 p-8 shadow-sm">
          <h3 className="text-xl font-bold text-amber-900">团队部署警告</h3>
          <div className="mt-4 space-y-2 text-sm leading-7 text-amber-800">
            {runtime.warnings.map((warning, index) => (
              <p key={`${warning}-${index}`}>- {warning}</p>
            ))}
          </div>
        </div>
      ) : null}

      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <h3 className="text-xl font-bold text-slate-950">团队快捷入口</h3>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link href="/admin" className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50">
            打开管理后台
          </Link>
          <Link href="/tasks" className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50">
            打开任务中心
          </Link>
          <Link href="/batch" className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50">
            打开批量出图
          </Link>
        </div>
      </div>
    </section>
  )
}
