import { AppShell } from "../../components/app-shell"
import { PagePlaceholder } from "../../components/page-placeholder"

export default function AdminPage() {
  return (
    <AppShell title="管理后台" subtitle="Admin Panel">
      <PagePlaceholder
        heading="管理后台骨架"
        description="后续会迁移系统配置、用户管理、模板管理、任务中心和审计能力。"
      />
    </AppShell>
  )
}
