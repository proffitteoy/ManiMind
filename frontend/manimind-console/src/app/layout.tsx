import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'ManiMind 控制台骨架',
  description: '用于承接 ManiMind 编排内核的前端控制台首页骨架。'
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang='zh-CN'>
      <body className='font-body antialiased'>{children}</body>
    </html>
  );
}
