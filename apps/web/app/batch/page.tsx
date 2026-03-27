import { AppShell } from "../../components/app-shell"
import { PagePlaceholder } from "../../components/page-placeholder"

export default function BatchPage() {
  return (
    <AppShell title="批量出图" subtitle="Batch Generation">
      <PagePlaceholder
        heading="批量出图工作区"
        description="后续会迁移现有 Streamlit 的素材上传、类型选择、图需生成、标题生成和后台任务能力。当前阶段先完成页面壳层与导航。"
      />
    </AppShell>
  )
}
