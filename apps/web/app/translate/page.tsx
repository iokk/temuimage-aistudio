import { AppShell } from "../../components/app-shell"
import { PagePlaceholder } from "../../components/page-placeholder"

export default function TranslatePage() {
  return (
    <AppShell title="图片翻译" subtitle="Image Translation">
      <PagePlaceholder
        heading="图片翻译工作区"
        description="后续会迁移图片翻译、OCR/翻译结果展示、后台任务和模型能力提示。当前阶段先完成页面骨架。"
      />
    </AppShell>
  )
}
