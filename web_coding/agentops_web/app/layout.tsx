import type { Metadata } from 'next';
import './globals.css';
import './product.css';

export const metadata: Metadata = {
  title: 'AgentOps Web',
  description: 'AgentOps 智能体观测控制台：执行追踪、性能分析与失败归因。',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
