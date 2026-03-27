import { AppShell } from "../../../components/app-shell"
import { PagePlaceholder } from "../../../components/page-placeholder"

export default function PersonalSettingsPage() {
  return (
    <AppShell title="个人模式" subtitle="Personal Settings">
      <PagePlaceholder
        heading="个人凭据配置"
        description="后续会迁移个人 Gemini Key、个人中转站 URL / Key / 模型配置能力。"
      />
    </AppShell>
  )
}
