import { AppShell } from "../../components/app-shell"
import { PagePlaceholder } from "../../components/page-placeholder"

export default function QuickPage() {
  return (
    <AppShell title="快速出图" subtitle="Quick Generation">
      <PagePlaceholder
        heading="快速出图工作区"
        description="后续会迁移快速出图的素材输入、类型选择、标题生成与后台任务能力。当前阶段先完成页面骨架。"
      />
    </AppShell>
  )
}
