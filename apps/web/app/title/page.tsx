import { AppShell } from "../../components/app-shell"
import { PagePlaceholder } from "../../components/page-placeholder"

export default function TitlePage() {
  return (
    <AppShell title="标题优化" subtitle="Title Optimization">
      <PagePlaceholder
        heading="标题优化工作区"
        description="后续会迁移图片+文字标题优化、标题模型切换和结果展示能力。当前阶段先完成页面骨架。"
      />
    </AppShell>
  )
}
