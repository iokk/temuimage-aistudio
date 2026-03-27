import { AppShell } from "../../../components/app-shell"
import { PagePlaceholder } from "../../../components/page-placeholder"

export default function TeamSettingsPage() {
  return (
    <AppShell title="团队/管理员" subtitle="Team Settings">
      <PagePlaceholder
        heading="团队系统配置"
        description="后续会迁移系统 Gemini、中转站、默认模型和角色权限配置。"
      />
    </AppShell>
  )
}
