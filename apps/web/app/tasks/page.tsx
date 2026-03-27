import { AppShell } from "../../components/app-shell"
import { PagePlaceholder } from "../../components/page-placeholder"

export default function TasksPage() {
  return (
    <AppShell title="任务中心" subtitle="Task Center">
      <PagePlaceholder
        heading="统一任务中心"
        description="后续会迁移批量出图、快速出图、标题优化、图片翻译的统一后台任务中心，并支持历史任务回看。"
      />
    </AppShell>
  )
}
