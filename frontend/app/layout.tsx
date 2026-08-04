import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI 狼人杀",
  description: "真人 × 多模型 AI 的文字狼人杀",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
