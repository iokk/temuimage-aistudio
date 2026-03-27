import "./globals.css"
import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "小白图 跨境电商出图系统 · AI Studio",
  description: "跨境电商出图、标题优化、图片翻译与任务中心",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
