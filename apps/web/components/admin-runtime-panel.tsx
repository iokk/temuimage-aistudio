import Link from "next/link"

import { getReadinessPayload, getRuntimePayload } from "../lib/runtime"

function renderBooleanLabel(value: boolean, trueText: string, falseText: string) {
  return value ? trueText : falseText
}

export async function AdminRuntimePanel() {
  const runtime = await getRuntimePayload()
  const readiness = await getReadinessPayload()

  if (!runtime) {
    return (
      <section className="rounded-3xl border border-amber-200 bg-amber-50 p-8 shadow-sm">
        <h3 className="text-2xl font-bold text-amber-900">运行诊断暂不可用</h3>
        <p className="mt-3 text-sm leading-7 text-amber-800">
          当前无法拉取 API 运行状态。请先确认 `NEXT_PUBLIC_API_BASE_URL` 指向的 FastAPI 服务已启动。
        </p>
      </section>
    )
  }

  return (
    <section className="grid gap-6">
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-500">API 版本</p>
          <p className="mt-2 text-2xl font-black text-slate-950">{runtime.app_version}</p>
          <p className="mt-2 text-sm text-slate-500">{runtime.app_name}</p>
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-500">任务存储</p>
          <p className="mt-2 text-2xl font-black text-slate-950">{runtime.active_backend}</p>
          <p className="mt-2 text-sm text-slate-500">期望后端：{runtime.preferred_backend}</p>
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-500">异步执行</p>
          <p className="mt-2 text-2xl font-black text-slate-950">{runtime.active_execution_backend}</p>
          <p className="mt-2 text-sm text-slate-500">期望执行：{runtime.preferred_execution_backend}</p>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <h3 className="text-xl font-bold text-slate-950">Readiness</h3>
        <p className="mt-4 text-sm leading-7 text-slate-600">
          当前状态：{readiness?.status || "unknown"}
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h3 className="text-xl font-bold text-slate-950">基础环境</h3>
          <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
            <p>认证方式：{runtime.auth_provider}</p>
            <p>{renderBooleanLabel(runtime.database_configured, "数据库连接已配置", "数据库连接未配置")}</p>
            <p>{renderBooleanLabel(runtime.redis_configured, "Redis 已配置", "Redis 未配置")}</p>
            <p>{renderBooleanLabel(runtime.persistence_ready, "任务存储已进入持久化模式", "任务存储仍在原型模式")}</p>
            <p>{renderBooleanLabel(runtime.execution_queue_ready, "任务执行已进入队列后端", "任务执行仍在 inline 模式")}</p>
            <p>{renderBooleanLabel(runtime.execution_storage_compatible, "执行后端与任务存储兼容", "执行后端与当前任务存储不兼容")}</p>
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h3 className="text-xl font-bold text-slate-950">回退提示</h3>
          <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
            <p>
              存储回退：{runtime.fallback_reason || "无，当前存储后端运行正常。"}
            </p>
            <p>
              执行回退：{runtime.execution_fallback_reason || "无，当前执行后端运行正常。"}
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <h3 className="text-xl font-bold text-slate-950">默认模型</h3>
        <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
          <p>标题模型：{runtime.default_title_model}</p>
          <p>图片翻译图像模型：{runtime.default_translate_image_model}</p>
          <p>图片翻译分析模型：{runtime.default_translate_analysis_model}</p>
          <p>快速出图图像模型：{runtime.default_quick_image_model}</p>
          <p>批量出图图像模型：{runtime.default_batch_image_model}</p>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <h3 className="text-xl font-bold text-slate-950">部署就绪度</h3>
        <p className="mt-4 text-sm leading-7 text-slate-600">
          {runtime.ready_for_distributed_workers
            ? "当前环境已经满足分布式 worker 运行条件。"
            : "当前环境还未满足分布式 worker 运行条件，请先处理下面的警告项。"}
        </p>
        <div className="mt-4 space-y-2 text-sm leading-7 text-slate-600">
          {runtime.warnings.length > 0 ? (
            runtime.warnings.map((warning, index) => (
              <p key={`${warning}-${index}`}>- {warning}</p>
            ))
          ) : (
            <p>- 当前没有阻塞部署的警告项。</p>
          )}
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <h3 className="text-xl font-bold text-slate-950">管理员快捷入口</h3>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            href="/tasks"
            className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50"
          >
            打开任务中心
          </Link>
          <Link
            href="/settings/team"
            className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50"
          >
            打开团队设置
          </Link>
        </div>
      </div>
    </section>
  )
}
