import { AppShell } from "../../components/app-shell"
import { PagePlaceholder } from "../../components/page-placeholder"

export default function LoginPage() {
  return (
    <AppShell title="登录" subtitle="Casdoor Authentication">
      <PagePlaceholder
        heading="统一登录入口"
        description="后续这里会接入 Casdoor，实现个人模式与团队模式的统一登录体验。当前阶段先完成 Auth.js + Casdoor 的接线骨架。"
      />
    </AppShell>
  )
}
